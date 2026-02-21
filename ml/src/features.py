"""
Feature engineering for the two-model tariff risk pipeline.

Country Model features:
  - Bilateral trade rolling stats (no forex — too sparse)
  - GSCPI global supply-chain index
  - US unemployment (optional macro context)
  - Event-history per country (rolling tariff counts, time since last)
  - Legal-authority history per country (rolling counts by authority type)

Sector Model features:
  - GSCPI global supply-chain index
  - Event-history per sector (rolling tariff counts, time since last)
  - Legal-authority history per sector

All rolling / history features use ONLY data up to month_start (no leakage).
Date in effect is NEVER included in any feature set.
"""

import re
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Feature column lists  (static base; authority columns are dynamic)
# ---------------------------------------------------------------------------

COUNTRY_FEATURE_COLS = [
    # Trade (country-level — bilateral deficit)
    "trade_deficit",
    "trade_deficit_3m_mean",
    "trade_deficit_3m_change",
    "imports",
    "exports",
    # Supply-chain stress (global)
    "gscpi",
    "gscpi_3m_mean",
    # US macro
    "unrate",
    # Time
    "month_of_year",
    "months_since_start",
    # Event-history (per country, past-only)
    "tariff_count_country_3m",
    "tariff_count_country_6m",
    "tariff_count_country_12m",
    "months_since_last_tariff_country",
]

SECTOR_FEATURE_COLS = [
    # Supply-chain stress (global)
    "gscpi",
    "gscpi_3m_mean",
    # Time
    "month_of_year",
    "months_since_start",
    # Event-history (per sector, past-only)
    "tariff_count_sector_3m",
    "tariff_count_sector_6m",
    "tariff_count_sector_12m",
    "months_since_last_tariff_sector",
]

COUNTRY_CAT_COLS = ["country_std"]
SECTOR_CAT_COLS  = ["sector_std"]

# Legacy (kept for backwards compat with api/main.py and old train.py)
FEATURE_COLS = COUNTRY_FEATURE_COLS
CAT_FEATURE_COLS = COUNTRY_CAT_COLS


# ---------------------------------------------------------------------------
# Authority normalisation
# ---------------------------------------------------------------------------

def _primary_authority(auth: str) -> str:
    """
    Collapse compound legal-authority strings to one primary label.
    E.g. "Section 232, 604, 301" -> "Section_232"
         "IEEPA"                 -> "IEEPA"
    """
    if not isinstance(auth, str) or not auth.strip():
        return "Unknown"
    a = auth.strip().upper()
    if "IEEPA"   in a: return "IEEPA"
    if "232"     in a: return "Section_232"
    if "301"     in a: return "Section_301"
    if "201"     in a: return "Section_201"
    if "USMCA"   in a: return "USMCA"
    # Sanitise whatever is left
    return re.sub(r"\W+", "_", auth.strip())[:30]


# ---------------------------------------------------------------------------
# Rolling helpers  (country-level, reused from old pipeline)
# ---------------------------------------------------------------------------

def _rolling_features_country(
    source_df: pd.DataFrame,
    key_col: str,
    value_cols: list,
    roll_mean_cols: list,
    roll_std_cols: list,
    diff_cols: list,
) -> pd.DataFrame:
    """
    For each entity in key_col, compute rolling/diff features on value_cols.
    Returns DataFrame indexed by (key_col, month).
    """
    frames = []
    for entity, grp in source_df.groupby(key_col, sort=False):
        g = grp.set_index("month").sort_index()
        f = pd.DataFrame(index=g.index)
        for col in value_cols:
            if col in g.columns:
                f[col] = g[col]
        for src, dst in roll_mean_cols:
            if src in g.columns:
                f[dst] = g[src].rolling(3, min_periods=1).mean()
        for src, dst in roll_std_cols:
            if src in g.columns:
                f[dst] = g[src].rolling(3, min_periods=1).std().fillna(0)
        for src, dst in diff_cols:
            if src in g.columns:
                f[dst] = g[src].diff(3)
        f[key_col] = entity
        frames.append(f.reset_index().rename(columns={"index": "month"}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Event-history features  (no leakage: only events <= month_start counted)
# ---------------------------------------------------------------------------

_TD_3M  = pd.Timedelta(days=91)
_TD_6M  = pd.Timedelta(days=182)
_TD_12M = pd.Timedelta(days=365)
_CAP_MONTHS = 36.0   # cap for "months since last tariff" when no history


def _compute_event_history(
    panel: pd.DataFrame,
    events: pd.DataFrame,
    key_col: str,
) -> pd.DataFrame:
    """
    Add rolling tariff-count and time-since-last-tariff columns to panel.
    Counts use ONLY event_date <= month_start (strict past, no leakage).
    """
    prefix     = key_col.replace("_std", "")   # "country" or "sector"
    cnt_3m_col = f"tariff_count_{prefix}_3m"
    cnt_6m_col = f"tariff_count_{prefix}_6m"
    cnt12_col  = f"tariff_count_{prefix}_12m"
    since_col  = f"months_since_last_tariff_{prefix}"

    results = []
    for entity, grp in panel.groupby(key_col, sort=False):
        ev_raw = events.loc[events[key_col] == entity, "event_date"].dropna()
        ev_arr = np.sort(ev_raw.values.astype("datetime64[ns]"))

        for _, row in grp.iterrows():
            t    = row["month_start"]
            t_ns = np.datetime64(t, "ns")

            past_all = ev_arr[ev_arr <= t_ns]
            c3  = int(np.sum(past_all >= np.datetime64(t - _TD_3M,  "ns")))
            c6  = int(np.sum(past_all >= np.datetime64(t - _TD_6M,  "ns")))
            c12 = int(np.sum(past_all >= np.datetime64(t - _TD_12M, "ns")))

            if len(past_all) == 0:
                months_since = _CAP_MONTHS
            else:
                days_since   = (t - pd.Timestamp(past_all[-1])).days
                months_since = round(days_since / 30.44, 2)

            results.append({
                key_col:     entity,
                "month_start": t,
                cnt_3m_col:  c3,
                cnt_6m_col:  c6,
                cnt12_col:   c12,
                since_col:   months_since,
            })

    hist_df = pd.DataFrame(results)
    return panel.merge(hist_df, on=[key_col, "month_start"], how="left")


# ---------------------------------------------------------------------------
# Legal-authority history features  (no leakage)
# ---------------------------------------------------------------------------

def _compute_authority_features(
    panel: pd.DataFrame,
    events: pd.DataFrame,
    key_col: str,
    top_n: int = 5,
) -> tuple:
    """
    For each (entity, month_start), count tariff events in past 12 months
    broken down by (normalised) legal authority.

    Returns: (augmented_panel, authority_col_names list)
    """
    if "legal_authority" not in events.columns:
        return panel, []

    # Normalise authority strings to primary labels
    ev = events.copy()
    ev["authority_primary"] = ev["legal_authority"].apply(_primary_authority)

    top_auths = (
        ev["authority_primary"].value_counts().head(top_n).index.tolist()
    )
    auth_cols = [f"authority_count_12m_{a}" for a in top_auths]

    results = []
    for entity, grp in panel.groupby(key_col, sort=False):
        ev_e = ev[ev[key_col] == entity].copy()
        ev_e["event_date"] = pd.to_datetime(ev_e["event_date"], errors="coerce")

        for _, row in grp.iterrows():
            t      = row["month_start"]
            t_12m  = t - _TD_12M
            past   = ev_e[
                (ev_e["event_date"] <= t) & (ev_e["event_date"] >= t_12m)
            ]
            rec = {key_col: entity, "month_start": t}
            for auth, col in zip(top_auths, auth_cols):
                rec[col] = int((past["authority_primary"] == auth).sum())
            results.append(rec)

    auth_df = pd.DataFrame(results)
    panel   = panel.merge(auth_df, on=[key_col, "month_start"], how="left")
    return panel, auth_cols


# ---------------------------------------------------------------------------
# GSCPI helper  (global, no entity dimension)
# ---------------------------------------------------------------------------

def _attach_gscpi(df: pd.DataFrame, gscpi_df: pd.DataFrame) -> pd.DataFrame:
    if gscpi_df.empty:
        return df
    gscpi = gscpi_df.set_index("month").sort_index()
    gscpi_ext = pd.DataFrame({
        "month":        gscpi.index,
        "gscpi":        gscpi["gscpi"].values,
        "gscpi_3m_mean": gscpi["gscpi"].rolling(3, min_periods=1).mean().values,
    })
    return df.merge(
        gscpi_ext, left_on="month_start", right_on="month", how="left"
    ).drop(columns=["month"], errors="ignore")


# ---------------------------------------------------------------------------
# Country model feature builder
# ---------------------------------------------------------------------------

def build_country_features(
    panel: pd.DataFrame,
    country_events: pd.DataFrame,
    bilateral_df: pd.DataFrame,
    gscpi_df: pd.DataFrame,
    unemployment_df: pd.DataFrame,
    top_n_authorities: int = 5,
) -> tuple:
    """
    Join all features onto the country panel.

    Returns
    -------
    (feature_df, all_numeric_cols, authority_col_names)
    feature_df columns: country_std, month_start, y, sample_weight, <feature cols>
    """
    df = panel.copy().sort_values(["country_std", "month_start"])

    # 1. Event-history features
    df = _compute_event_history(df, country_events, "country_std")

    # 2. Authority-history features
    df, auth_cols = _compute_authority_features(
        df, country_events, "country_std", top_n=top_n_authorities
    )

    # 3. Bilateral trade rolling stats
    #    bilateral_df.country is normalised the same way as country_std
    if not bilateral_df.empty:
        trade_feat = _rolling_features_country(
            bilateral_df.rename(columns={"country": "country_std"}),
            key_col="country_std",
            value_cols=["trade_deficit", "imports", "exports"],
            roll_mean_cols=[("trade_deficit", "trade_deficit_3m_mean")],
            roll_std_cols=[],
            diff_cols=[("trade_deficit", "trade_deficit_3m_change")],
        )
        if not trade_feat.empty:
            merge_cols = [
                c for c in [
                    "country_std", "month",
                    "trade_deficit", "imports", "exports",
                    "trade_deficit_3m_mean", "trade_deficit_3m_change",
                ] if c in trade_feat.columns
            ]
            df = df.merge(
                trade_feat[merge_cols],
                left_on=["country_std", "month_start"],
                right_on=["country_std", "month"],
                how="left",
            ).drop(columns=["month"], errors="ignore")

    # 4. GSCPI
    df = _attach_gscpi(df, gscpi_df)

    # 5. Unemployment (US macro; optional — drop if empty)
    if not unemployment_df.empty:
        df = df.merge(
            unemployment_df.rename(columns={"month": "_um"}),
            left_on="month_start", right_on="_um", how="left",
        ).drop(columns=["_um"], errors="ignore")

    # 6. Time features
    df["month_of_year"] = df["month_start"].dt.month
    min_m = df["month_start"].min()
    df["months_since_start"] = (
        (df["month_start"].dt.year  - min_m.year)  * 12 +
        (df["month_start"].dt.month - min_m.month)
    )

    # 7. Ensure all base feature cols exist
    all_num_cols = COUNTRY_FEATURE_COLS + auth_cols
    for col in all_num_cols:
        if col not in df.columns:
            df[col] = np.nan

    return df.reset_index(drop=True), all_num_cols, auth_cols


# ---------------------------------------------------------------------------
# Sector model feature builder
# ---------------------------------------------------------------------------

def build_sector_features(
    panel: pd.DataFrame,
    sector_events: pd.DataFrame,
    gscpi_df: pd.DataFrame,
    top_n_authorities: int = 5,
) -> tuple:
    """
    Join all features onto the sector panel.

    Returns
    -------
    (feature_df, all_numeric_cols, authority_col_names)
    feature_df columns: sector_std, month_start, y, sample_weight, <feature cols>
    """
    df = panel.copy().sort_values(["sector_std", "month_start"])

    # 1. Event-history features
    df = _compute_event_history(df, sector_events, "sector_std")

    # 2. Authority-history features
    df, auth_cols = _compute_authority_features(
        df, sector_events, "sector_std", top_n=top_n_authorities
    )

    # 3. GSCPI
    df = _attach_gscpi(df, gscpi_df)

    # 4. Time features
    df["month_of_year"] = df["month_start"].dt.month
    min_m = df["month_start"].min()
    df["months_since_start"] = (
        (df["month_start"].dt.year  - min_m.year)  * 12 +
        (df["month_start"].dt.month - min_m.month)
    )

    # 5. Ensure all base feature cols exist
    all_num_cols = SECTOR_FEATURE_COLS + auth_cols
    for col in all_num_cols:
        if col not in df.columns:
            df[col] = np.nan

    return df.reset_index(drop=True), all_num_cols, auth_cols


# ---------------------------------------------------------------------------
# Legacy helpers  (kept so api/main.py and old code paths still import)
# ---------------------------------------------------------------------------

def build_features(
    panel: pd.DataFrame,
    bilateral_df: pd.DataFrame,
    forex_df: pd.DataFrame,      # ignored — forex removed (too sparse)
    gscpi_df: pd.DataFrame,
    manufacturing_df: pd.DataFrame,  # ignored — too sparse
    polrisk_df: pd.DataFrame,        # ignored — too sparse
    unemployment_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Legacy single-model feature builder.  Delegates to build_country_features()
    using a dummy empty events frame (no event-history features).
    """
    dummy_events = pd.DataFrame(
        columns=["country_std", "event_date", "legal_authority", "is_mass_rollout"]
    )
    # panel may have "country" not "country_std" — add it
    if "country_std" not in panel.columns and "country" in panel.columns:
        panel = panel.copy()
        panel["country_std"] = panel["country"]
    if "sample_weight" not in panel.columns:
        panel = panel.copy()
        panel["sample_weight"] = 1.0

    feature_df, _, _ = build_country_features(
        panel, dummy_events, bilateral_df, gscpi_df, unemployment_df
    )
    # Restore "country" column for backwards compat
    if "country" not in feature_df.columns and "country_std" in feature_df.columns:
        feature_df["country"] = feature_df["country_std"]
    return feature_df


def get_feature_matrix(df: pd.DataFrame) -> tuple:
    """Legacy: extract (X, y) using FEATURE_COLS + CAT_FEATURE_COLS."""
    x_cols = CAT_FEATURE_COLS + FEATURE_COLS
    X = df[[c for c in x_cols if c in df.columns]].copy()
    y = df["y"].copy() if "y" in df.columns else None
    return X, y

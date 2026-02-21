"""
Build monthly (entity, month_start, y, sample_weight) training panels.

Two independent models are trained:
  Country panel : (country_std, month_start, y)  -- economy/general tariff events
  Sector panel  : (sector_std,  month_start, y)  -- sector-specific tariff events

Label definition (no leakage):
    y = 1  if any tariff event for the entity falls in [month_start, month_start + 3 months)
            i.e. the event occurs in month t, t+1, or t+2.
            Only event_date = "First announced" is used — Date in effect is NEVER used.

Mass-rollout handling (IMPORTANT):
    When >= MASS_ROLLOUT_THRESHOLD entities share the same (event_date, legal_authority),
    it is flagged as a single sweeping policy announcement.

    Panel rows whose positive label comes EXCLUSIVELY from mass-rollout events
    receive sample_weight=MASS_ROLLOUT_WEIGHT. If there is ANY non-mass event in the
    label window, sample_weight stays 1.0.
"""

import pandas as pd
import numpy as np

from .standardize import derive_sector

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
H_MONTHS = 3                 # look-ahead window in months (t, t+1, t+2)
MASS_ROLLOUT_THRESHOLD = 10  # min entities sharing same event_date+authority

# Downweight mass-rollout-only positives MORE aggressively to reduce April dominating
MASS_ROLLOUT_WEIGHT = 0.05

PANEL_START_DEFAULT = pd.Timestamp("2024-11-01")

# After normalize_sector(), economy/general rows have this label
_COUNTRY_SECTORS = {"General"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mark_mass_rollout(events_df: pd.DataFrame) -> pd.Series:
    """
    Return a boolean Series (same index as events_df).
    True if the row belongs to a cluster where >= MASS_ROLLOUT_THRESHOLD
    entities share the same (event_date, legal_authority).
    """
    if "event_date" not in events_df.columns or "legal_authority" not in events_df.columns:
        return pd.Series(False, index=events_df.index)

    counts = events_df.groupby(
        [events_df["event_date"].dt.to_period("D"), "legal_authority"]
    )["event_date"].transform("count")
    return counts >= MASS_ROLLOUT_THRESHOLD


# ---------------------------------------------------------------------------
# Tariff event extraction
# ---------------------------------------------------------------------------

def build_country_events(tariff_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract (country_std, event_date, legal_authority, is_mass_rollout) for
    economy-level / GENERAL sector tariff actions using event_date only.

    Filters: sector_std == "General"  OR  target_type == "Economy".
    """
    is_general = tariff_df["sector_std"].isin(_COUNTRY_SECTORS)
    is_economy = tariff_df["target_type"].astype(str).str.strip().str.lower() == "economy"
    sub = tariff_df[is_general | is_economy].copy()

    cty_col  = "country_std" if "country_std" in sub.columns else "geography"
    auth_col = "legal_authority" if "legal_authority" in sub.columns else None

    rows = []
    for _, r in sub.iterrows():
        dt = r.get("event_date", r.get("announced_date"))
        if pd.isna(dt):
            continue
        country = str(r.get(cty_col, "")).strip().upper()
        if not country or country in ("NAN", ""):
            continue
        rows.append({
            "country_std":     country,
            "event_date":      pd.Timestamp(dt),
            "legal_authority": str(r[auth_col]) if auth_col else "Unknown",
        })

    if not rows:
        return pd.DataFrame(columns=["country_std", "event_date", "legal_authority", "is_mass_rollout"])

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["country_std", "event_date"])
        .reset_index(drop=True)
    )
    df["is_mass_rollout"] = _mark_mass_rollout(df)
    return df


def build_sector_events(tariff_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract (sector_std, event_date, legal_authority, is_mass_rollout) for
    sector-specific tariff actions using event_date only.

    Filters: sector_std != "General".
    """
    is_specific = ~tariff_df["sector_std"].isin(_COUNTRY_SECTORS)
    sub = tariff_df[is_specific].copy()

    auth_col = "legal_authority" if "legal_authority" in sub.columns else None

    rows = []
    for _, r in sub.iterrows():
        dt = r.get("event_date", r.get("announced_date"))
        if pd.isna(dt):
            continue
        sector = str(r.get("sector_std", "")).strip()
        if not sector or sector.lower() == "nan":
            continue
        rows.append({
            "sector_std":      sector,
            "event_date":      pd.Timestamp(dt),
            "legal_authority": str(r[auth_col]) if auth_col else "Unknown",
        })

    if not rows:
        return pd.DataFrame(columns=["sector_std", "event_date", "legal_authority", "is_mass_rollout"])

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["sector_std", "event_date"])
        .reset_index(drop=True)
    )
    df["is_mass_rollout"] = _mark_mass_rollout(df)
    return df


# ---------------------------------------------------------------------------
# Generic panel builder
# ---------------------------------------------------------------------------

def _build_panel(
    events: pd.DataFrame,
    key_col: str,
    feature_start: pd.Timestamp,
    feature_end: pd.Timestamp | None,
) -> pd.DataFrame:
    """
    Cross-join unique entities × monthly calendar, assign labels and sample weights.

    Returns: (key_col, month_start, y, sample_weight)
    """
    if events is None or events.empty or key_col not in events.columns:
        return pd.DataFrame(columns=[key_col, "month_start", "y", "sample_weight"])

    # IMPORTANT: do NOT default to "now" (creates future months with no data)
    if feature_end is None:
        if "event_date" in events.columns and events["event_date"].notna().any():
            feature_end = events["event_date"].max().to_period("M").to_timestamp()
        else:
            feature_end = feature_start

    feature_start = pd.Timestamp(feature_start).to_period("M").to_timestamp()
    feature_end   = pd.Timestamp(feature_end).to_period("M").to_timestamp()

    months   = pd.date_range(feature_start, feature_end, freq="MS")
    entities = pd.Series(events[key_col].dropna().unique()).astype(str).tolist()

    panel = pd.DataFrame([(e, m) for e in entities for m in months], columns=[key_col, "month_start"])

    panel = panel.merge(
        events[[key_col, "event_date", "is_mass_rollout"]],
        on=key_col,
        how="left",
    )

    end_window = (panel["month_start"].dt.to_period("M") + H_MONTHS).dt.to_timestamp()

    within_window = (
        panel["event_date"].notna()
        & (panel["event_date"] >= panel["month_start"])
        & (panel["event_date"] < end_window)
    )
    panel["y"] = within_window.astype(int)

    is_mass = panel["is_mass_rollout"].fillna(False)
    panel["_pos_non_mass"] = (within_window & ~is_mass).astype(int)
    panel["_pos_mass"]     = (within_window &  is_mass).astype(int)

    panel = (
        panel.groupby([key_col, "month_start"], sort=False)
        .agg(
            y=("y", "max"),
            any_non_mass=("_pos_non_mass", "max"),
            any_mass=("_pos_mass", "max"),
        )
        .reset_index()
    )
    panel["y"] = panel["y"].fillna(0).astype(int)

    panel["sample_weight"] = 1.0
    mask = (panel["y"] == 1) & (panel["any_non_mass"] == 0) & (panel["any_mass"] == 1)
    panel.loc[mask, "sample_weight"] = MASS_ROLLOUT_WEIGHT

    panel = panel.drop(columns=["any_non_mass", "any_mass"])
    return panel.sort_values([key_col, "month_start"]).reset_index(drop=True)


def build_country_panel(
    country_events: pd.DataFrame,
    feature_start: pd.Timestamp | None = None,
    feature_end:   pd.Timestamp | None = None,
) -> pd.DataFrame:
    if feature_start is None:
        feature_start = PANEL_START_DEFAULT
    return _build_panel(country_events, "country_std", feature_start, feature_end)


def build_sector_panel(
    sector_events: pd.DataFrame,
    feature_start: pd.Timestamp | None = None,
    feature_end:   pd.Timestamp | None = None,
) -> pd.DataFrame:
    if feature_start is None:
        feature_start = PANEL_START_DEFAULT
    return _build_panel(sector_events, "sector_std", feature_start, feature_end)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def panel_stats(panel: pd.DataFrame) -> dict:
    key_cols = [c for c in ("country_std", "sector_std", "country", "sector") if c in panel.columns]
    n_pos   = int(panel["y"].sum()) if "y" in panel.columns else 0
    n_total = len(panel)
    mass_rows = int((panel.get("sample_weight", pd.Series(1.0)) < 1.0).sum()) if n_total else 0
    return {
        "n_total":        n_total,
        "n_positive":     n_pos,
        "n_negative":     n_total - n_pos,
        "positive_rate":  round(n_pos / n_total, 4) if n_total else 0,
        "mass_rollout_downweighted": mass_rows,
        "unique_entities": int(panel[key_cols].drop_duplicates().shape[0]) if key_cols and n_total else 0,
        "months":         int(panel["month_start"].nunique()) if n_total and "month_start" in panel.columns else 0,
    }


# ---------------------------------------------------------------------------
# Backwards-compatibility shims
# ---------------------------------------------------------------------------

def build_tariff_events(tariff_df: pd.DataFrame) -> pd.DataFrame:
    has_sector_std = "sector_std" in tariff_df.columns
    rows = []
    for _, r in tariff_df.iterrows():
        country = r.get("geography")
        sector  = r.get("sector_std") if has_sector_std and pd.notna(r.get("sector_std")) \
                  else derive_sector(str(r.get("target", "")))
        dt = r.get("event_date") or r.get("announced_date")
        if pd.notna(dt):
            rows.append({"country": country, "sector": sector, "event_date": dt})
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
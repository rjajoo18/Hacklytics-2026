"""
Feature engineering: join all economic data onto the (country, sector, month_start) panel.

All rolling windows use only past data (no leakage):
  - rolling(3).mean() at month T uses months T-2, T-1, T  (min_periods=1)
  - diff(3) at month T = value(T) - value(T-3)
"""

import numpy as np
import pandas as pd


# Feature column definitions (used by model.py for column ordering)
FEATURE_COLS = [
    # Trade
    "trade_deficit",
    "trade_deficit_3m_mean",
    "trade_deficit_3m_change",
    "imports",
    "exports",
    # Forex
    "fx_usd",
    "fx_3m_mean",
    "fx_3m_std",
    # GSCPI (global)
    "gscpi",
    "gscpi_3m_mean",
    # Manufacturing
    "manuf_X_T",
    "manuf_M_T",
    "manuf_X_Manuf",
    "manuf_M_Manuf",
    "manuf_X_MHT",
    "manuf_M_MHT",
    # Political risk
    "pol_risk_score",
    "pol_risk_3m_change",
    # Unemployment (US macro)
    "unrate",
    "unrate_3m_mean",
    # Time
    "month_of_year",
    "months_since_start",
]

CAT_FEATURE_COLS = ["country", "sector"]


# ---------------------------------------------------------------------------
# Rolling helpers (applied per-group to avoid cross-group leakage)
# ---------------------------------------------------------------------------

def _rolling_features_country(
    source_df: pd.DataFrame,
    value_cols: list[str],
    roll_mean_cols: list[tuple[str, str]],   # (src_col, dst_col)
    roll_std_cols:  list[tuple[str, str]],
    diff_cols:      list[tuple[str, str]],
) -> pd.DataFrame:
    """
    For each country, compute rolling/diff features on value_cols,
    returning a DataFrame indexed by (country, month).
    """
    frames = []
    for country, grp in source_df.groupby("country", sort=False):
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
        f["country"] = country
        frames.append(f.reset_index().rename(columns={"index": "month"}))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Main feature builder
# ---------------------------------------------------------------------------

def build_features(
    panel: pd.DataFrame,
    bilateral_df: pd.DataFrame,
    forex_df: pd.DataFrame,
    gscpi_df: pd.DataFrame,
    manufacturing_df: pd.DataFrame,
    polrisk_df: pd.DataFrame,
    unemployment_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join all feature data onto the panel rows.
    Missing values are left as NaN; callers should impute as needed.

    Returns panel + FEATURE_COLS + CAT_FEATURE_COLS columns.
    """
    df = panel.copy().sort_values(["country", "sector", "month_start"])

    # ------------------------------------------------------------------
    # 1. Bilateral Trade Features
    # ------------------------------------------------------------------
    if not bilateral_df.empty:
        trade_feat = _rolling_features_country(
            bilateral_df,
            value_cols=["trade_deficit", "imports", "exports"],
            roll_mean_cols=[("trade_deficit", "trade_deficit_3m_mean")],
            roll_std_cols=[],
            diff_cols=[("trade_deficit", "trade_deficit_3m_change")],
        )
        if not trade_feat.empty:
            df = df.merge(
                trade_feat[["country", "month", "trade_deficit", "imports", "exports",
                            "trade_deficit_3m_mean", "trade_deficit_3m_change"]],
                left_on=["country", "month_start"],
                right_on=["country", "month"],
                how="left",
            ).drop(columns=["month"], errors="ignore")

    # ------------------------------------------------------------------
    # 2. Forex Features
    # ------------------------------------------------------------------
    if not forex_df.empty:
        fx_feat = _rolling_features_country(
            forex_df,
            value_cols=["fx_usd"],
            roll_mean_cols=[("fx_usd", "fx_3m_mean")],
            roll_std_cols=[("fx_usd", "fx_3m_std")],
            diff_cols=[],
        )
        if not fx_feat.empty:
            df = df.merge(
                fx_feat[["country", "month", "fx_usd", "fx_3m_mean", "fx_3m_std"]],
                left_on=["country", "month_start"],
                right_on=["country", "month"],
                how="left",
            ).drop(columns=["month"], errors="ignore")

    # ------------------------------------------------------------------
    # 3. GSCPI Features (global — no country dimension)
    # ------------------------------------------------------------------
    if not gscpi_df.empty:
        gscpi = gscpi_df.set_index("month").sort_index()
        gscpi_ext = pd.DataFrame({
            "month": gscpi.index,
            "gscpi": gscpi["gscpi"].values,
            "gscpi_3m_mean": gscpi["gscpi"].rolling(3, min_periods=1).mean().values,
        })
        df = df.merge(gscpi_ext, left_on="month_start", right_on="month", how="left"
                      ).drop(columns=["month"], errors="ignore")

    # ------------------------------------------------------------------
    # 4. Manufacturing Features
    # ------------------------------------------------------------------
    manuf_val_cols = [c for c in manufacturing_df.columns
                      if c.startswith("manuf_")]
    if manuf_val_cols and not manufacturing_df.empty:
        # Forward-fill to fill any quarterly/annual → monthly gaps
        manuf_long = manufacturing_df.copy()
        manuf_long = manuf_long.sort_values(["country", "month"])
        # Build a complete monthly index per country and forward-fill
        manuf_frames = []
        for country, grp in manuf_long.groupby("country", sort=False):
            g = grp.set_index("month")[manuf_val_cols].sort_index()
            # Reindex to monthly, then ffill
            full_idx = pd.date_range(g.index.min(), g.index.max(), freq="MS")
            g = g.reindex(full_idx).ffill()
            g.index.name = "month"
            g["country"] = country
            manuf_frames.append(g.reset_index())
        if manuf_frames:
            manuf_feat = pd.concat(manuf_frames, ignore_index=True)
            df = df.merge(
                manuf_feat[["country", "month"] + manuf_val_cols],
                left_on=["country", "month_start"],
                right_on=["country", "month"],
                how="left",
            ).drop(columns=["month"], errors="ignore")

    # ------------------------------------------------------------------
    # 5. Political Risk Features
    # ------------------------------------------------------------------
    if not polrisk_df.empty:
        pr_feat = _rolling_features_country(
            polrisk_df,
            value_cols=["pol_risk_score"],
            roll_mean_cols=[],
            roll_std_cols=[],
            diff_cols=[("pol_risk_score", "pol_risk_3m_change")],
        )
        # Also add global political risk (Target_Entity = "GLOBAL") for all rows
        global_pr = polrisk_df[polrisk_df["country"] == "GLOBAL"].copy()
        if not global_pr.empty:
            global_pr = global_pr.rename(columns={"pol_risk_score": "global_pol_risk"})
            df = df.merge(
                global_pr[["month", "global_pol_risk"]],
                left_on="month_start", right_on="month", how="left"
            ).drop(columns=["month"], errors="ignore")

        if not pr_feat.empty:
            df = df.merge(
                pr_feat[["country", "month", "pol_risk_score", "pol_risk_3m_change"]],
                left_on=["country", "month_start"],
                right_on=["country", "month"],
                how="left",
            ).drop(columns=["month"], errors="ignore")

        # Fill per-country pol_risk with global where missing
        if "global_pol_risk" in df.columns:
            if "pol_risk_score" not in df.columns:
                df["pol_risk_score"] = df["global_pol_risk"]
            else:
                df["pol_risk_score"] = df["pol_risk_score"].fillna(df["global_pol_risk"])
            df.drop(columns=["global_pol_risk"], inplace=True, errors="ignore")

    # ------------------------------------------------------------------
    # 6. Unemployment (US macro — no country dimension)
    # ------------------------------------------------------------------
    if not unemployment_df.empty:
        unemp = unemployment_df.set_index("month").sort_index()
        unemp_ext = pd.DataFrame({
            "month": unemp.index,
            "unrate": unemp["unrate"].values,
            "unrate_3m_mean": unemp["unrate"].rolling(3, min_periods=1).mean().values,
        })
        df = df.merge(unemp_ext, left_on="month_start", right_on="month", how="left"
                      ).drop(columns=["month"], errors="ignore")

    # ------------------------------------------------------------------
    # 7. Time Features
    # ------------------------------------------------------------------
    df["month_of_year"] = df["month_start"].dt.month
    min_month = df["month_start"].min()
    df["months_since_start"] = (
        (df["month_start"].dt.year - min_month.year) * 12 +
        (df["month_start"].dt.month - min_month.month)
    )

    # ------------------------------------------------------------------
    # 8. Ensure all FEATURE_COLS exist (fill missing with NaN)
    # ------------------------------------------------------------------
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = np.nan

    return df.reset_index(drop=True)


def get_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series | None]:
    """
    Extract (X, y) from the full panel+features DataFrame.
    X contains CAT_FEATURE_COLS + FEATURE_COLS.
    y is None if 'y' column is absent (inference mode).
    """
    x_cols = CAT_FEATURE_COLS + FEATURE_COLS
    X = df[[c for c in x_cols if c in df.columns]].copy()
    y = df["y"].copy() if "y" in df.columns else None
    return X, y

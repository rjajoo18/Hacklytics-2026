"""
Build the monthly (country, sector, month_start, y) training panel.

Label definition:
    y = 1  if any tariff event for (country, sector) falls in
              (month_start, month_start + H days]
    y = 0  otherwise

H defaults to 90 days.
"""

import pandas as pd
import numpy as np

from .standardize import derive_sector

H_DAYS = 90


def build_tariff_events(tariff_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract normalised (country, sector, event_date) rows from the tariff tracker.
    Both announced_date and effective_date (when not NaT) are treated as events.
    """
    rows = []
    for _, r in tariff_df.iterrows():
        country = r["geography"]
        sector = derive_sector(str(r["target"]))
        for date_col in ("announced_date", "effective_date"):
            dt = r[date_col]
            if pd.notna(dt):
                rows.append({"country": country, "sector": sector, "event_date": dt})
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def build_monthly_panel(
    tariff_events: pd.DataFrame,
    feature_start: pd.Timestamp | None = None,
    feature_end:   pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Cross-join unique (country, sector) combos × monthly calendar,
    then assign label y=1 if any event falls in the forward 90-day window.

    Parameters
    ----------
    tariff_events : output of build_tariff_events()
    feature_start : first month_start to include (defaults to 2020-01-01)
    feature_end   : last  month_start to include (defaults to current month)

    Returns
    -------
    DataFrame with columns: country, sector, month_start, y
    """
    if feature_start is None:
        feature_start = pd.Timestamp("2020-01-01")
    if feature_end is None:
        feature_end = pd.Timestamp.now().to_period("M").to_timestamp()

    months = pd.date_range(feature_start, feature_end, freq="MS")

    combos = (tariff_events[["country", "sector"]]
              .drop_duplicates()
              .reset_index(drop=True))

    # Expand: each combo × every month
    panel = pd.DataFrame(
        [(c, s, m)
         for (_, (c, s)) in combos.iterrows()
         for m in months],
        columns=["country", "sector", "month_start"],
    )

    # Merge events onto panel (each combo row may join to multiple events)
    panel = panel.merge(
        tariff_events[["country", "sector", "event_date"]],
        on=["country", "sector"],
        how="left",
    )

    # Label: event within (month_start, month_start + H]
    delta = pd.Timedelta(days=H_DAYS)
    panel["y"] = (
        panel["event_date"].notna() &
        (panel["event_date"] > panel["month_start"]) &
        (panel["event_date"] <= panel["month_start"] + delta)
    ).astype(int)

    # Collapse duplicates (take max y per group)
    panel = (panel.groupby(["country", "sector", "month_start"], sort=False)["y"]
             .max()
             .reset_index())
    panel["y"] = panel["y"].fillna(0).astype(int)

    return panel.sort_values(["country", "sector", "month_start"]).reset_index(drop=True)


def panel_stats(panel: pd.DataFrame) -> dict:
    n_pos = int(panel["y"].sum())
    n_total = len(panel)
    return {
        "n_total": n_total,
        "n_positive": n_pos,
        "n_negative": n_total - n_pos,
        "positive_rate": round(n_pos / n_total, 4) if n_total else 0,
        "unique_combos": int(panel[["country", "sector"]].drop_duplicates().shape[0]),
        "months": int(panel["month_start"].nunique()),
    }

"""
Load and clean all raw CSV data sources into consistent long-format DataFrames.

Each loader returns a DataFrame with at minimum a 'month' column (pd.Timestamp,
always normalized to month-start) and a 'country' column where applicable.
"""

import os
import re
import warnings
import numpy as np
import pandas as pd

from .standardize import normalize_country

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_RAW = os.path.join(os.path.dirname(__file__), "..", "Trained_models", "raw")

BILATERAL_PATH    = os.path.join(_RAW, "bilateral trade deficits .csv")
FOREX_PATH        = os.path.join(_RAW, "forex_data.csv")
GSCPI_PATH        = os.path.join(_RAW, "GSCPI Monthly Data-Table 1.csv")
MANUFACTURING_PATH = os.path.join(_RAW, "manufacturing_data.csv")
POLRISK_PATH      = os.path.join(_RAW, "political_risk_data.csv")
UNEMPLOYMENT_PATH = os.path.join(_RAW, "unemployment.csv")
TARIFF_PATH       = os.path.join(_RAW, "Trump tariff tracker - All actions.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_MONTH_ABB = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _month_start(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.to_period("M").to_timestamp()


# ---------------------------------------------------------------------------
# Bilateral Trade Deficits
# ---------------------------------------------------------------------------
def load_bilateral_trade() -> pd.DataFrame:
    """
    Returns columns: country, month, imports, exports, trade_deficit
    (trade_deficit = imports - exports; positive = US trade deficit with country)
    Values are in millions USD.
    """
    df = pd.read_csv(BILATERAL_PATH)
    df["country"] = df["CTYNAME"].apply(normalize_country)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["year"])

    import_cols = {c: _MONTH_ABB[c[1:]] for c in df.columns
                   if c.startswith("I") and c[1:] in _MONTH_ABB}
    export_cols = {c: _MONTH_ABB[c[1:]] for c in df.columns
                   if c.startswith("E") and c[1:] in _MONTH_ABB}

    records: list[dict] = []
    for _, row in df.iterrows():
        yr = int(row["year"])
        country = row["country"]
        for icol, m in import_cols.items():
            ecol = "E" + icol[1:]
            imp = pd.to_numeric(row.get(icol), errors="coerce")
            exp = pd.to_numeric(row.get(ecol), errors="coerce")
            if pd.isna(imp) and pd.isna(exp):
                continue
            records.append({
                "country": country,
                "month": pd.Timestamp(year=yr, month=m, day=1),
                "imports": imp,
                "exports": exp,
            })

    result = pd.DataFrame(records)
    result["trade_deficit"] = result["imports"] - result["exports"]
    return result.sort_values(["country", "month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Forex Data (IMF)
# ---------------------------------------------------------------------------
def load_forex() -> pd.DataFrame:
    """
    Returns columns: country, month, fx_usd
    fx_usd = domestic currency per 1 USD (higher → weaker local currency).
    Monthly frequency only.
    """
    df = pd.read_csv(FOREX_PATH)
    # Identify monthly period columns
    month_cols = [c for c in df.columns if re.match(r"^\d{4}-M\d{2}$", c)]
    if not month_cols:
        return pd.DataFrame(columns=["country", "month", "fx_usd"])

    # Prefer EoP, then Period Average; prefer "Domestic currency per US Dollar"
    for tf in ("End-of-period", "Period average"):
        mask = (
            (df["FREQUENCY"] == "Monthly") &
            (df["INDICATOR"].str.contains("Domestic currency per US Dollar", na=False)) &
            (df["TYPE_OF_TRANSFORMATION"].str.contains(tf, na=False))
        )
        if mask.sum() > 0:
            break

    if mask.sum() == 0:
        # Last fallback: any monthly row with USD indicator
        mask = (
            (df["FREQUENCY"] == "Monthly") &
            (df["INDICATOR"].str.contains("US Dollar", na=False))
        )

    sub = df.loc[mask, ["COUNTRY"] + month_cols].copy()
    sub["COUNTRY"] = sub["COUNTRY"].apply(normalize_country)

    long = sub.melt(id_vars="COUNTRY", var_name="period", value_name="fx_usd")
    long["month"] = pd.to_datetime(
        long["period"].str.replace("-M", "-", regex=False), format="%Y-%m", errors="coerce"
    )
    long["fx_usd"] = pd.to_numeric(long["fx_usd"], errors="coerce")
    long = long.dropna(subset=["month", "fx_usd"]).rename(columns={"COUNTRY": "country"})

    # One row per (country, month) — take mean if duplicates
    result = (long.groupby(["country", "month"])["fx_usd"]
              .mean().reset_index()
              .sort_values(["country", "month"]))
    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# GSCPI Monthly
# ---------------------------------------------------------------------------
def load_gscpi() -> pd.DataFrame:
    """
    Returns columns: month, gscpi
    Global Supply Chain Pressure Index (NY Fed). Monthly since 1998.
    """
    raw = pd.read_csv(GSCPI_PATH, header=None, usecols=[0, 1],
                      names=["Date", "gscpi"])
    # Keep only rows where Date looks like a real date (e.g. "31-Jan-1998")
    raw["date_parsed"] = pd.to_datetime(raw["Date"], format="%d-%b-%Y", errors="coerce")
    raw = raw.dropna(subset=["date_parsed"])
    raw["gscpi"] = pd.to_numeric(raw["gscpi"], errors="coerce")
    raw = raw.dropna(subset=["gscpi"])
    raw["month"] = raw["date_parsed"].apply(_month_start)
    return raw[["month", "gscpi"]].sort_values("month").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Manufacturing Data (UN Comtrade / OECD)
# ---------------------------------------------------------------------------
def _parse_year_col(s: str) -> pd.Timestamp:
    """Parse '2025 M01', '2025 Q1', or '2025' into a month-start Timestamp."""
    s = str(s).strip()
    if re.match(r"^\d{4} M\d{2}$", s):
        return pd.to_datetime(s.replace(" M", "-"), format="%Y-%m", errors="coerce")
    if re.match(r"^\d{4} Q\d$", s):
        q = int(s[-1])
        return pd.Timestamp(year=int(s[:4]), month=(q - 1) * 3 + 1, day=1)
    if re.match(r"^\d{4}$", s):
        return pd.Timestamp(year=int(s), month=1, day=1)
    return pd.NaT


def load_manufacturing() -> pd.DataFrame:
    """
    Returns a wide DataFrame: country, month, X_T, M_T, X_Manuf, M_Manuf, X_MHT, M_MHT
    Values are in USD.  Quarterly/annual rows are assigned to the first month of
    their period; callers should forward-fill to monthly as needed.
    """
    df = pd.read_csv(MANUFACTURING_PATH)
    df["month"] = df["Year"].apply(_parse_year_col)
    df = df.dropna(subset=["month"])
    df["country"] = df["Country"].apply(normalize_country)
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

    useful_vars = ["X_T", "M_T", "X_Manuf", "M_Manuf", "X_MHT", "M_MHT"]
    df = df[df["VariableCode"].isin(useful_vars)].copy()

    pivot = (
        df.pivot_table(index=["country", "month"], columns="VariableCode",
                       values="Value", aggfunc="mean")
        .reset_index()
    )
    pivot.columns.name = None
    # Rename variable cols to avoid collision
    rename = {v: f"manuf_{v}" for v in useful_vars if v in pivot.columns}
    pivot = pivot.rename(columns=rename)
    return pivot.sort_values(["country", "month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Political Risk Data
# ---------------------------------------------------------------------------
def load_political_risk() -> pd.DataFrame:
    """
    Returns columns: country, month, pol_risk_score
    Monthly mean Political_Risk_Score aggregated per Target_Entity.
    Also returns a global_pol_risk_score for 'GLOBAL' entries.
    """
    df = pd.read_csv(POLRISK_PATH)
    df["month"] = pd.to_datetime(df["pub_date"], errors="coerce").apply(
        lambda x: _month_start(x) if pd.notna(x) else pd.NaT
    )
    df = df.dropna(subset=["month"])
    df["country"] = df["Target_Entity"].apply(normalize_country)
    df["Political_Risk_Score"] = pd.to_numeric(df["Political_Risk_Score"], errors="coerce")

    monthly = (
        df.groupby(["country", "month"])["Political_Risk_Score"]
        .mean()
        .reset_index()
        .rename(columns={"Political_Risk_Score": "pol_risk_score"})
        .sort_values(["country", "month"])
    )
    return monthly.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Unemployment (US)
# ---------------------------------------------------------------------------
def load_unemployment() -> pd.DataFrame:
    """
    Returns columns: month, unrate
    US civilian unemployment rate (FRED UNRATE). Monthly.
    """
    df = pd.read_csv(UNEMPLOYMENT_PATH)
    df["month"] = pd.to_datetime(df["observation_date"], errors="coerce").apply(
        lambda x: _month_start(x) if pd.notna(x) else pd.NaT
    )
    df["unrate"] = pd.to_numeric(df["UNRATE"], errors="coerce")
    return (df[["month", "unrate"]].dropna()
            .sort_values("month").reset_index(drop=True))


# ---------------------------------------------------------------------------
# Tariff Tracker
# ---------------------------------------------------------------------------
def load_tariff_tracker() -> pd.DataFrame:
    """
    Returns columns: target_type, geography, target, announced_date, effective_date
    announced_date / effective_date are pd.Timestamp (NaT where TBD).
    """
    df = pd.read_csv(TARIFF_PATH, on_bad_lines="skip", encoding="utf-8")
    # Keep only the columns we need (first 5)
    df = df.iloc[:, :5].copy()
    df.columns = ["target_type", "geography", "target", "announced_date", "effective_date"]

    def _safe_date(s):
        if pd.isna(s) or "TBD" in str(s).upper():
            return pd.NaT
        return pd.to_datetime(str(s), format="%m/%d/%Y", errors="coerce")

    df["announced_date"] = df["announced_date"].apply(_safe_date)
    df["effective_date"] = df["effective_date"].apply(_safe_date)
    df["geography"] = df["geography"].apply(normalize_country)
    df["target_type"] = df["target_type"].fillna("Other")

    return df.dropna(subset=["announced_date"]).reset_index(drop=True)

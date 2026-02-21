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

from .standardize import normalize_country, normalize_sector, derive_sector

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_RAW = os.path.join(os.path.dirname(__file__), "..", "Trained_models", "raw")

BILATERAL_PATH         = os.path.join(_RAW, "bilateral trade deficits .csv")
FOREX_PATH             = os.path.join(_RAW, "forex_data.csv")
GSCPI_PATH             = os.path.join(_RAW, "GSCPI Monthly Data-Table 1.csv")
MANUFACTURING_PATH     = os.path.join(_RAW, "manufacturing_data.csv")
POLRISK_PATH           = os.path.join(_RAW, "political_risk_data.csv")
UNEMPLOYMENT_PATH      = os.path.join(_RAW, "unemployment.csv")
TARIFF_PATH            = os.path.join(_RAW, "Trump tariff tracker - All actions.csv")
COUNTRY_STD_MAP_PATH   = os.path.join(_RAW, "country_name.csv")
COUNTRY_FEATURES_PATH  = os.path.join(_RAW, "country_month_features.csv")


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
    def _norm_cols(cols):
        out = []
        for c in cols:
            c = str(c).strip()
            c = re.sub(r"\s+", " ", c)
            c = c.lower()
            c = re.sub(r"[^a-z0-9]+", "_", c)
            c = re.sub(r"_+", "_", c).strip("_")
            out.append(c)
        return out

    def _to_num(x):
        if pd.isna(x):
            return np.nan
        s = str(x).strip()
        if s == "":
            return np.nan
        s = s.replace(",", "").replace("$", "")
        return pd.to_numeric(s, errors="coerce")

    # 1) Read CSV robustly
    df = pd.read_csv(BILATERAL_PATH)

    # ---- NEW LONG FORMAT: already has imports/exports/month_start columns ----
    if all(c in df.columns for c in ("imports", "exports", "month_start")):
        country_col = next(
            (c for c in ("country_std", "country_raw", "ctyname", "CTYNAME", "country")
             if c in df.columns),
            None,
        )
        if country_col is None:
            raise ValueError("Bilateral trade CSV (long format): no country column found.")
        df["country"] = df[country_col].apply(normalize_country)
        df["month"] = pd.to_datetime(df["month_start"], errors="coerce").apply(
            lambda x: _month_start(x) if pd.notna(x) else pd.NaT
        )
        df["imports"] = pd.to_numeric(df["imports"], errors="coerce")
        df["exports"] = pd.to_numeric(df["exports"], errors="coerce")
        df = df.dropna(subset=["country", "month"])
        df["trade_deficit"] = df["imports"] - df["exports"]
        return (
            df[["country", "month", "imports", "exports", "trade_deficit"]]
            .sort_values(["country", "month"])
            .reset_index(drop=True)
        )
    # -------------------------------------------------------------------------

    # If we got a single mega-column, delimiter is wrong; try common separators
    if df.shape[1] == 1:
        for sep in ("\t", "|", ";"):
            try:
                df2 = pd.read_csv(BILATERAL_PATH, sep=sep)
                if df2.shape[1] > 1:
                    df = df2
                    break
            except Exception:
                pass

    # If still RangeIndex columns, header likely missing/offset; try skipping metadata rows
    if isinstance(df.columns, pd.RangeIndex):
        for k in (0, 1, 2, 3, 4, 5):
            try:
                df2 = pd.read_csv(BILATERAL_PATH, skiprows=k)
                if not isinstance(df2.columns, pd.RangeIndex) and df2.shape[1] > 1:
                    df = df2
                    break
            except Exception:
                pass

    # 2) Normalize columns
    orig_cols = list(df.columns)
    df.columns = _norm_cols(df.columns)

    # 3) Identify key columns (country + year)
    # Country candidates
    country_candidates = [
        "ctyname", "country", "country_name", "partner", "partner_name", "geography", "cty"
    ]
    country_col = next((c for c in country_candidates if c in df.columns), None)
    if country_col is None:
        # Last-resort: pick a column that contains the substring "cty" or "country"
        for c in df.columns:
            if "country" in c or "cty" in c or "name" in c:
                country_col = c
                break
    if country_col is None:
        raise ValueError(
            "Bilateral trade CSV: couldn't find a country column. "
            f"Parsed columns: {df.columns.tolist()} (original: {orig_cols})"
        )

    # Year candidates
    year_candidates = ["year", "yr", "calendar_year"]
    year_col = next((c for c in year_candidates if c in df.columns), None)
    if year_col is None:
        # sometimes "time" or "date" holds year
        for c in df.columns:
            if c in ("time", "date") or c.endswith("_year"):
                year_col = c
                break
    if year_col is None:
        raise ValueError(
            "Bilateral trade CSV: couldn't find a year column. "
            f"Parsed columns: {df.columns.tolist()} (original: {orig_cols})"
        )

    df["country"] = df[country_col].apply(normalize_country)
    df["year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    df = df.dropna(subset=["year", "country"])

    # 4) Find monthly import/export columns
    # We support patterns like:
    #   IJAN, I_JAN, imports_jan, import_jan
    #   EJAN, E_JAN, exports_jan, export_jan
    month_tokens = set(_MONTH_ABB.keys())

    def _extract_month_token(colname: str) -> str | None:
        # returns 'JAN'...'DEC' if found
        up = colname.upper()
        for tok in month_tokens:
            if re.search(rf"\b{tok}\b", up):
                return tok
        # also handle compact like IJAN / EJAN with no separators
        m = re.search(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)", up)
        return m.group(1) if m else None

    import_cols = {}  # col -> month_num
    export_cols = {}  # col -> month_num

    for c in df.columns:
        tok = _extract_month_token(c)
        if not tok:
            continue

        # classify as import vs export
        # import indicators
        if re.match(r"^i", c) or "import" in c:
            import_cols[c] = _MONTH_ABB[tok]
        # export indicators
        if re.match(r"^e", c) or "export" in c:
            export_cols[c] = _MONTH_ABB[tok]

    # If we detected imports but not exports (or vice versa), try pairing by month token anyway
    if not import_cols and not export_cols:
        raise ValueError(
            "Bilateral trade CSV: couldn't detect monthly import/export columns. "
            f"Parsed columns: {df.columns.tolist()} (original: {orig_cols})"
        )

    # 5) Build long records
    records: list[dict] = []
    for _, row in df.iterrows():
        yr = int(row["year"])
        country = row["country"]

        # Build month -> value maps for this row
        imp_by_m = {}
        exp_by_m = {}

        for c, m in import_cols.items():
            imp_by_m[m] = _to_num(row.get(c))

        for c, m in export_cols.items():
            exp_by_m[m] = _to_num(row.get(c))

        months = sorted(set(imp_by_m.keys()) | set(exp_by_m.keys()))
        for m in months:
            imp = imp_by_m.get(m, np.nan)
            exp = exp_by_m.get(m, np.nan)
            if pd.isna(imp) and pd.isna(exp):
                continue
            records.append({
                "country": country,
                "month": pd.Timestamp(year=yr, month=m, day=1),
                "imports": imp,
                "exports": exp,
            })

    result = pd.DataFrame(records)

    # Ensure columns exist even if one side was missing
    if "imports" not in result.columns:
        result["imports"] = np.nan
    if "exports" not in result.columns:
        result["exports"] = np.nan

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

    # ---- NEW LONG FORMAT: has 'value' and 'month_start' columns ----
    if "value" in df.columns and "month_start" in df.columns:
        for tf in ("End-of-period (EoP)", "End-of-period", "Period average"):
            mask = (
                (df["FREQUENCY"] == "Monthly") &
                (df["INDICATOR"].str.contains("Domestic currency per US Dollar", na=False)) &
                (df["TYPE_OF_TRANSFORMATION"].str.contains(tf, na=False))
            )
            if mask.sum() > 0:
                break
        if mask.sum() == 0:
            mask = (
                (df["FREQUENCY"] == "Monthly") &
                (df["INDICATOR"].str.contains("US Dollar", na=False))
            )
        sub = df.loc[mask].copy()
        country_col = "country_std" if "country_std" in sub.columns else "COUNTRY"
        sub["country"] = sub[country_col].apply(normalize_country)
        sub["month"] = pd.to_datetime(sub["month_start"], errors="coerce").apply(
            lambda x: _month_start(x) if pd.notna(x) else pd.NaT
        )
        sub["fx_usd"] = pd.to_numeric(sub["value"], errors="coerce")
        sub = sub.dropna(subset=["country", "month", "fx_usd"])
        result = (
            sub.groupby(["country", "month"])["fx_usd"]
            .mean().reset_index()
            .sort_values(["country", "month"])
        )
        return result.reset_index(drop=True)
    # -----------------------------------------------------------------

    # Identify monthly period columns (old wide format)
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
    Returns columns: target_type, geography, target,
                     announced_date (= First announced, parsed),
                     effective_date (= Date in effect, parsed — for metadata only),
                     event_date     (= announced_date; the label source),
                     legal_authority, sector_std, country_std.

    LEAKAGE NOTE: effective_date / Date in effect is intentionally excluded from
    all model feature sets.  It is returned here solely for UI / metadata display.
    Labels (y) are always derived from event_date = First announced.
    """
    raw = pd.read_csv(TARIFF_PATH, on_bad_lines="skip", encoding="utf-8")

    # --- Core five columns ---
    _core = ["Target type", "Geography", "Target", "First announced", "Date in effect"]
    if all(c in raw.columns for c in _core):
        df = raw[_core].copy()
    else:
        df = raw.iloc[:, :5].copy()
    df.columns = ["target_type", "geography", "target", "announced_date", "effective_date"]
    # df.index is identical to raw.index here (no rows dropped yet)

    def _safe_date(s):
        if pd.isna(s) or "TBD" in str(s).upper():
            return pd.NaT
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y"):
            try:
                return pd.to_datetime(str(s), format=fmt)
            except Exception:
                pass
        return pd.to_datetime(str(s), errors="coerce")

    df["announced_date"] = df["announced_date"].apply(_safe_date)
    df["effective_date"] = df["effective_date"].apply(_safe_date)
    df["geography"] = df["geography"].apply(normalize_country)
    df["target_type"] = df["target_type"].fillna("Other").str.strip()

    # --- event_date: prefer pre-parsed column, else use announced_date ---
    for col in ("event_date", "First announced_parsed"):
        if col in raw.columns:
            df["event_date"] = pd.to_datetime(raw[col], errors="coerce").values
            break
    else:
        df["event_date"] = df["announced_date"]

    # --- Legal authority ---
    if "Legal authority" in raw.columns:
        df["legal_authority"] = raw["Legal authority"].fillna("Unknown").values
    else:
        df["legal_authority"] = "Unknown"

    # --- sector_std: use file's UPPERCASE value (normalized to canonical label) ---
    if "sector_std" in raw.columns:
        df["sector_std"] = pd.Series(raw["sector_std"].values, index=df.index).apply(
            normalize_sector
        )
    else:
        df["sector_std"] = df["target"].apply(derive_sector)

    # --- country_std from file ---
    if "country_std" in raw.columns:
        df["country_std"] = (
            pd.Series(raw["country_std"].values, index=df.index)
            .fillna("").str.strip().str.upper()
        )
    else:
        df["country_std"] = df["geography"]

    return df.dropna(subset=["announced_date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Country Standardization Map  (country_name.csv)
# ---------------------------------------------------------------------------
def load_country_std_map() -> dict:
    """
    Load country_name.csv and return a lookup dict:
        uppercase(country_raw) -> country_std
    Used to assign a consistent country_std key to panel rows so they can
    join with country_month_features.csv.
    """
    if not os.path.exists(COUNTRY_STD_MAP_PATH):
        return {}
    try:
        df = pd.read_csv(COUNTRY_STD_MAP_PATH)
    except (pd.errors.EmptyDataError, Exception):
        return {}
    if df.empty or "country_raw" not in df.columns or "country_std" not in df.columns:
        return {}
    return {
        str(row["country_raw"]).strip().upper(): str(row["country_std"]).strip().upper()
        for _, row in df.iterrows()
    }


# ---------------------------------------------------------------------------
# Pre-aligned Feature Table  (country_month_features.csv)
# ---------------------------------------------------------------------------
def load_country_month_features() -> pd.DataFrame:
    """
    Load the pre-aligned feature table.
    Expected columns: country_std, month_start (YYYY-MM-01), <feature cols>.
    Returns an empty DataFrame if the file is missing or has no rows yet.
    """
    if not os.path.exists(COUNTRY_FEATURES_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(COUNTRY_FEATURES_PATH)
    except (pd.errors.EmptyDataError, Exception):
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()

    # Detect the month column
    _month_candidates = ("month_start", "month", "date", "period")
    month_col = next(
        (c for c in df.columns if c.lower() in _month_candidates), None
    )
    if month_col is None:
        # Fallback: first column whose values parse as dates >50% of the time
        for c in df.columns:
            if pd.to_datetime(df[c], errors="coerce").notna().mean() > 0.5:
                month_col = c
                break
    if month_col is None:
        return pd.DataFrame()

    df["month_start"] = (
        pd.to_datetime(df[month_col], errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    if month_col != "month_start":
        df = df.drop(columns=[month_col])
    df = df.dropna(subset=["month_start"])

    # Normalize country column to country_std
    country_col = next(
        (c for c in df.columns if "country" in c.lower()), None
    )
    if country_col and country_col != "country_std":
        df = df.rename(columns={country_col: "country_std"})
    if "country_std" not in df.columns:
        return pd.DataFrame()

    df["country_std"] = df["country_std"].astype(str).str.strip().str.upper()
    return df.reset_index(drop=True)

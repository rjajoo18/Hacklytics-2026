import json
import os
import numpy as np
import pandas as pd

DEFAULT_AUTH_WEIGHTS = {
    "IEEPA": 1.0,
    "SECTION_301": 0.8,
    "SECTION 301": 0.8,
    "SECTION_232": 0.6,
    "SECTION 232": 0.6,
    "OTHER": 0.4,
    "UNKNOWN": 0.4,
}

def _norm_authority(x: str) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "UNKNOWN"
    s = str(x).strip().upper()
    s = s.replace("-", "_").replace(" ", "_")
    return s

def compute_country_multipliers(
    tariff_df: pd.DataFrame,
    window_days: int = 365,
    min_mult: float = 0.5,
    max_mult: float = 2.0,
    auth_weights: dict | None = None,
) -> dict:
    """
    Returns dict: {COUNTRY_STD: multiplier in [min_mult, max_mult]}
    Uses only observable policy actions from tariff_df.
    """
    if auth_weights is None:
        auth_weights = DEFAULT_AUTH_WEIGHTS

    if "event_date" not in tariff_df.columns:
        raise ValueError("tariff_df must contain 'event_date' (parsed) column")

    df = tariff_df.copy()
    df = df[df["event_date"].notna()].copy()
    if df.empty:
        return {}

    as_of = pd.to_datetime(df["event_date"]).max()
    start = as_of - pd.Timedelta(days=window_days)
    df = df[pd.to_datetime(df["event_date"]) >= start].copy()

    if "country_std" not in df.columns:
        # fall back if needed
        if "Geography" in df.columns:
            df["country_std"] = df["Geography"].astype(str).str.strip().str.upper()
        else:
            raise ValueError("tariff_df must contain 'country_std' or 'Geography'")

    df["country_std"] = df["country_std"].astype(str).str.strip().str.upper()

    # authority severity
    auth_col = None
    for c in ["legal_authority", "Legal authority", "authority"]:
        if c in df.columns:
            auth_col = c
            break
    if auth_col is None:
        df["_auth"] = "UNKNOWN"
    else:
        df["_auth"] = df[auth_col].apply(_norm_authority)

    df["_auth_w"] = df["_auth"].map(lambda a: float(auth_weights.get(a, auth_weights.get("OTHER", 0.4))))

    g = df.groupby("country_std", as_index=False).agg(
        count_12m=("event_date", "count"),
        severity_12m=("_auth_w", "sum"),
    )

    # raw score (stable, monotone)
    g["raw_score"] = np.log1p(g["count_12m"].astype(float)) + 0.7 * np.log1p(g["severity_12m"].astype(float))
    med = float(np.median(g["raw_score"].values)) if len(g) else 1.0
    if med <= 1e-9:
        med = 1.0

    g["multiplier"] = g["raw_score"] / med
    g["multiplier"] = g["multiplier"].clip(lower=min_mult, upper=max_mult)

    return dict(zip(g["country_std"], g["multiplier"].round(4).tolist()))

def save_country_multipliers(mult: dict, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(mult, f, indent=2, sort_keys=True)

def load_country_multipliers(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)
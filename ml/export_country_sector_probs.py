"""
Export country × sector tariff risk table for Supabase.

FAST version:
- Compute sector model probabilities once per sector
- Apply per-country multiplier (0.5–2.0)
- Build full matrix

Run from project root:
    python export_country_sector_probs.py

Output:
    artifacts/country_sector_tariff_probs.csv
"""

import os
import json
import joblib
import pandas as pd

from src.model import _predict_from_pkg  # uses your existing inference helper

ARTIFACTS_DIR = "artifacts"


def clamp(x: float, lo: float = 0.0, hi: float = 0.99) -> float:
    return float(max(lo, min(hi, x)))


def make_id(country: str, sector: str) -> str:
    clean_country = str(country).strip().upper().replace(" ", "_")
    clean_sector = (
        str(sector).strip().upper()
        .replace(" ", "_")
        .replace("&", "AND")
        .replace("/", "_")
    )
    return f"{clean_country}_{clean_sector}"


# -----------------------------
# Load sector model artifacts
# -----------------------------
model_path = os.path.join(ARTIFACTS_DIR, "model_sector.pkl")
scaler_path = os.path.join(ARTIFACTS_DIR, "scaler_sector.pkl")
panel_path = os.path.join(ARTIFACTS_DIR, "feature_panel_sector.csv")
schema_path = os.path.join(ARTIFACTS_DIR, "feature_schema_sector.json")

if not os.path.exists(model_path):
    raise FileNotFoundError("artifacts/model_sector.pkl not found. Run train.py first.")
if not os.path.exists(panel_path):
    raise FileNotFoundError("artifacts/feature_panel_sector.csv not found. Run train.py first.")
if not os.path.exists(schema_path):
    raise FileNotFoundError("artifacts/feature_schema_sector.json not found. Run train.py first.")

sector_model = joblib.load(model_path)
sector_scaler = joblib.load(scaler_path)
sector_panel = pd.read_csv(panel_path, parse_dates=["month_start"])

with open(schema_path) as f:
    sector_meta = json.load(f)

sector_pkg = dict(sector_meta)
sector_pkg["model"] = sector_model
sector_pkg["scaler"] = sector_scaler
sector_pkg["feature_panel"] = sector_panel

# -----------------------------
# Load country multipliers
# -----------------------------
mult_path = os.path.join(ARTIFACTS_DIR, "country_multipliers.json")
if not os.path.exists(mult_path):
    raise FileNotFoundError(
        "artifacts/country_multipliers.json not found. "
        "You need to save these during train.py."
    )

with open(mult_path) as f:
    country_multipliers = json.load(f)

countries = sorted(country_multipliers.keys())

# -----------------------------
# Compute sector probabilities ONCE
# -----------------------------
sectors = sorted(sector_panel["sector_std"].dropna().astype(str).unique())

print(f"Countries: {len(countries)}")
print(f"Sectors:   {len(sectors)}")

sector_prob = {}
for sector in sectors:
    s_res = _predict_from_pkg(sector, "sector_std", sector_pkg)
    sector_prob[sector] = float(s_res.get("tariff_risk_prob", 0.0))

# -----------------------------
# Build full matrix
# -----------------------------
rows = []
for country in countries:
    m = float(country_multipliers.get(country, 1.0))
    for sector in sectors:
        base_p = sector_prob.get(sector, 0.0)
        p = clamp(base_p * m)

        rows.append({
            "id": make_id(country, sector),     # <- primary key for Supabase
            "country": country,
            "sector": sector,
            "sector_base_prob": round(base_p, 6),
            "country_multiplier": round(m, 6),
            "tariff_risk_prob": round(p, 6),
            "tariff_risk_pct": f"{round(p * 100, 1)}%",
        })

df_out = pd.DataFrame(rows)

out_path = os.path.join(ARTIFACTS_DIR, "country_sector_tariff_probs.csv")
df_out.to_csv(out_path, index=False)

print(f"\nExport complete: {out_path}")
print(f"Total rows: {len(df_out)}")
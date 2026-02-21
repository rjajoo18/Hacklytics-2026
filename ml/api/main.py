"""
FastAPI — Tariff Risk Forecasting endpoint.

Run with:
    uvicorn api.main:app --reload

Endpoint:
    GET /predict?country=China&sector=Semiconductor

Response:
    {
      "mode": "probability" | "risk_score",
      "tariff_risk_prob": 0.73,          # null if risk_score mode
      "tariff_risk_score": 73.0,         # 0-100
      "top_drivers": [...],
      "country": "CHINA",
      "sector": "Semiconductor",
      "as_of_month": "2025-11-01"
    }
"""

from __future__ import annotations

import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse

from src.standardize import normalize_country, derive_sector
from src.model import load_artifacts, predict_single, ARTIFACTS_DIR

app = FastAPI(
    title="Tariff Risk Forecasting API",
    description=(
        "Given a (country, sector) pair, returns the probability of a US tariff "
        "action within the next 90 days, or a composite risk score when supervised "
        "training data is insufficient."
    ),
    version="1.0.0",
)

_model_pkg: dict | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _model_pkg
    try:
        _model_pkg = load_artifacts(ARTIFACTS_DIR)
        print(f"[API] Model loaded — mode={_model_pkg['mode']}, "
              f"n_positive={_model_pkg['n_positive']}")
    except FileNotFoundError:
        print("[API] WARNING: No artifacts found. Run train.py first.")
        _model_pkg = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": _model_pkg is not None,
        "mode": _model_pkg["mode"] if _model_pkg else None,
    }


@app.get("/predict")
def predict(
    country: str = Query(..., description="Country name, e.g. 'China' or 'European Union'"),
    sector:  str = Query("General", description="Sector, e.g. 'Semiconductor', 'Automotive'"),
) -> JSONResponse:
    if _model_pkg is None:
        raise HTTPException(
            status_code=503,
            detail="Model artifacts not found. Please run train.py first.",
        )

    norm_country = normalize_country(country)
    norm_sector  = sector.strip() if sector.strip() else "General"

    result = predict_single(norm_country, norm_sector, _model_pkg)

    # Ensure null-safe JSON
    if result.get("tariff_risk_prob") is None:
        result.pop("tariff_risk_prob", None)

    return JSONResponse(content=result)


@app.get("/countries")
def list_countries() -> dict:
    """Return all countries in the training panel."""
    if _model_pkg is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    panel = _model_pkg["feature_panel"]
    countries = sorted(panel["country"].dropna().unique().tolist())
    return {"countries": countries}


@app.get("/sectors")
def list_sectors() -> dict:
    """Return all sectors in the training panel."""
    if _model_pkg is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    panel = _model_pkg["feature_panel"]
    sectors = sorted(panel["sector"].dropna().unique().tolist())
    return {"sectors": sectors}

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hacklytics 2026 project analyzing U.S. tariff policy impact on economic indicators. Two independent subsystems:

1. **Political Document Scraper** — `Trained_models/sentiment_analysis.py`
2. **Tariff Risk Forecasting Pipeline** — `src/`, `api/`, `train.py`

## Setup

```bash
pip install -r requirements.txt
```

`.env` file requires `OPENROUTER_API_KEY=sk-or-...` (for the scraper only).

## Running

```bash
# Scraper (generates political_risk_data.csv)
python Trained_models/sentiment_analysis.py

# Forecasting pipeline: train model, save artifacts
python train.py

# Start prediction API on :8000
uvicorn api.main:app --reload
```

**Prediction endpoint:**
```
GET /predict?country=China&sector=Semiconductor
GET /predict?country=Canada&sector=General
```

## Architecture

### 1. Political Document Scraper (`Trained_models/sentiment_analysis.py`)

```
Web Scraper -> LLM Extraction -> Risk Scoring -> CSV Output
```

Scrapes 20 government URLs (federalregister.gov, whitehouse.gov, congress.gov, ustr.gov), calls Google Gemini 2.5 Flash Lite via OpenRouter API (`openrouter.ai/api/v1/chat/completions`). Extracts `Target_Entity`, `Action_Type`, `Imminence_Score`, `Summary`. Risk score = `Action_Type_Weight * Imminence_Score * 100`. Output: `political_risk_data.csv`.

### 2. Tariff Risk Forecasting Pipeline

```
Raw CSVs -> tariff_events -> monthly panel (y=1/0) -> features -> CatBoost -> FastAPI
```

| File | Purpose |
|------|---------|
| `src/standardize.py` | `normalize_country()` with alias dict; `derive_sector()` via keyword matching on tariff Target text |
| `src/data_loader.py` | One loader per CSV; all return long-format DataFrames with `month` (month-start Timestamp) and `country` |
| `src/panel.py` | `build_monthly_panel()` creates `(country, sector, month_start, y)` where `y=1` if any tariff event falls in `(month_start, month_start+90d]` |
| `src/features.py` | Joins all data sources onto panel; per-country rolling 3-month mean/std/diff (no leakage); `FEATURE_COLS` defines column order |
| `src/model.py` | `train()` selects model path; `predict_single()` for inference; `save/load_artifacts()` |
| `api/main.py` | FastAPI with `/predict`, `/health`, `/countries`, `/sectors` endpoints; loads artifacts at startup |
| `train.py` | Orchestrates full pipeline; smoke-tests 5 country-sector pairs at end |

**Model selection logic** (`src/model.py:train`):
- `n_positive >= 50` → `CatBoostClassifier` (time-based 80/20 split, `scale_pos_weight` for imbalance, PR-AUC eval). Current data: 502 positives, PR-AUC ~0.40.
- `1 <= n_positive < 50` → `LogisticRegression(C=0.05)` coefficients used as risk-score weights
- `n_positive == 0` → pure heuristic (`_HEURISTIC_WEIGHTS` dict prioritizing `pol_risk_3m_change`, `trade_deficit`, `gscpi`, `fx_3m_std`)

**Artifacts saved to `artifacts/`:** `model.pkl`, `scaler.pkl`, `feature_panel.csv`, `model_meta.json`

### Data Assets (`Trained_models/raw/`)

| File | Notes |
|------|-------|
| `bilateral trade deficits .csv` | US bilateral imports/exports 1997-present; wide format with `IJAN`-`IDEC` / `EJAN`-`EDEC` month columns |
| `forex_data.csv` | IMF exchange rates 2025-2026; period columns like `2025-M01`; filtered to monthly + "Domestic currency per US Dollar" |
| `GSCPI Monthly Data-Table 1.csv` | NY Fed GSCPI 1998-present; first 4 rows are metadata, actual data starts row 5 |
| `manufacturing_data.csv` | UN Comtrade stats; `Year` column in `2025 M01` format; multiple `VariableCode` rows per country-month |
| `Trump tariff tracker - All actions.csv` | Primary label source; `Target type` (Economy/Sector/Other), `Geography`, `Target`, `First announced`, `Date in effect` |
| `unemployment.csv` | US UNRATE monthly (FRED); US-wide macro feature |
| `political_risk_data.csv` | Output of scraper; aggregated to monthly `pol_risk_score` per `Target_Entity` |

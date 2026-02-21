# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hacklytics 2026 project analyzing U.S. tariff policy impact on economic indicators. The pipeline scrapes official government documents, uses LLM-based extraction to score tariff actions, and combines this with economic datasets (forex, manufacturing, unemployment, GSCPI) for analysis.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with:
```
OPENROUTER_API_KEY=sk-or-...
```

## Running

```bash
python sentiment_analysis.py
```

Outputs `political_risk_data.csv` to the Desktop (with fallback to OneDrive/Documents/home).

## Architecture

### Data Pipeline

```
Web Scraper → LLM Extraction → Risk Scoring → CSV Output
```

**`sentiment_analysis.py`** — the main and only application file (444 lines):

1. **Web Scraping** (lines 205–249): Scrapes 20 hardcoded government URLs across `federalregister.gov`, `whitehouse.gov`, `congress.gov`, and `ustr.gov` using BeautifulSoup with multiple CSS selector fallbacks.

2. **LLM Analysis** (lines 268–304): Calls Google Gemini 2.5 Flash Lite via the OpenRouter API (`https://openrouter.ai/api/v1/chat/completions`). Extracts structured fields from each document:
   - `Target_Entity` — who the tariff targets
   - `Action_Type` — one of: Enacted, Modified, Proposed, Investigated, Revoked, Other
   - `Imminence_Score` — float 0.0–1.0 representing urgency
   - `Summary` — one-sentence description

3. **Risk Scoring** (lines 323–327): `Political_Risk_Score = Action_Type_Weight × Imminence_Score × 100`. Action type weights range from `1.00` (Enacted) to `-0.60` (Revoked).

4. **Deduplication & Persistence** (lines 339–353): Tracks seen URLs to avoid re-processing; appends to existing CSV.

### Data Assets (`data/raw/`)

| File | Description |
|------|-------------|
| `forex_data.csv` | Foreign exchange rates (1.7 MB) |
| `manufacturing_data.csv` | Manufacturing indicators (595 KB) |
| `GSCPI Monthly Data-Table 1.csv` | Global Supply Chain Pressure Index |
| `Trump tariff tracker - All actions.csv` | Comprehensive tariff action tracker |
| `unemployment.csv` | Unemployment data |
| `political_risk_data.csv` | Generated output from the scraper |

### Empty Directories

`api/`, `artifacts/`, and `src/` are currently empty — intended for future API layer, model artifacts, and source modules.

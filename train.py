"""
End-to-end Tariff Risk Forecasting pipeline.

Steps:
  1. Load all raw CSV data
  2. Build tariff events from the tracker
  3. Build monthly (country, sector, month_start, y) panel
  4. Engineer features
  5. Train model (CatBoost / LogReg / heuristic depending on label count)
  6. Save artifacts to artifacts/

Usage:
    python train.py
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore")

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd

from src.data_loader import (
    load_bilateral_trade,
    load_forex,
    load_gscpi,
    load_manufacturing,
    load_political_risk,
    load_unemployment,
    load_tariff_tracker,
)
from src.panel import build_tariff_events, build_monthly_panel, panel_stats
from src.features import build_features
from src.model import train, save_artifacts


def run_pipeline(verbose: bool = True) -> None:
    def log(msg: str) -> None:
        if verbose:
            print(msg)

    os.makedirs("artifacts", exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Load raw data
    # ------------------------------------------------------------------
    log("\n=== Step 1: Loading raw data ===")

    log("  bilateral_trade_deficits...")
    bilateral_df = load_bilateral_trade()
    log(f"    => {len(bilateral_df):,} rows, {bilateral_df['country'].nunique()} countries")

    log("  forex_data...")
    forex_df = load_forex()
    log(f"    => {len(forex_df):,} rows, {forex_df['country'].nunique() if not forex_df.empty else 0} countries")

    log("  GSCPI...")
    gscpi_df = load_gscpi()
    log(f"    => {len(gscpi_df):,} monthly observations ({gscpi_df['month'].min().date()} - {gscpi_df['month'].max().date()})")

    log("  manufacturing_data...")
    manufacturing_df = load_manufacturing()
    log(f"    => {len(manufacturing_df):,} rows, {manufacturing_df['country'].nunique() if not manufacturing_df.empty else 0} countries")

    log("  political_risk_data...")
    polrisk_df = load_political_risk()
    log(f"    => {len(polrisk_df):,} entity-month observations")

    log("  unemployment...")
    unemployment_df = load_unemployment()
    log(f"    => {len(unemployment_df):,} monthly observations")

    log("  tariff_tracker...")
    tariff_df = load_tariff_tracker()
    log(f"    => {len(tariff_df):,} tariff actions, "
        f"{tariff_df['geography'].nunique()} geographies")

    # ------------------------------------------------------------------
    # Step 2: Build tariff events
    # ------------------------------------------------------------------
    log("\n=== Step 2: Building tariff events ===")
    tariff_events = build_tariff_events(tariff_df)
    log(f"  => {len(tariff_events):,} unique (country, sector, event_date) events")
    log(f"  => {tariff_events['country'].nunique()} countries, "
        f"{tariff_events['sector'].nunique()} sectors")
    log(f"  Sector distribution:\n{tariff_events['sector'].value_counts().to_string()}")

    # ------------------------------------------------------------------
    # Step 3: Build monthly panel
    # ------------------------------------------------------------------
    log("\n=== Step 3: Building monthly panel ===")
    panel = build_monthly_panel(
        tariff_events,
        feature_start=pd.Timestamp("2020-01-01"),
    )
    stats = panel_stats(panel)
    log(f"  Panel shape: {panel.shape}")
    log(f"  Stats: {stats}")

    # ------------------------------------------------------------------
    # Step 4: Feature engineering
    # ------------------------------------------------------------------
    log("\n=== Step 4: Feature engineering ===")
    feature_df = build_features(
        panel,
        bilateral_df,
        forex_df,
        gscpi_df,
        manufacturing_df,
        polrisk_df,
        unemployment_df,
    )
    log(f"  Feature matrix shape: {feature_df.shape}")
    non_null_pct = (feature_df.notna().mean() * 100).round(1)
    log("  Feature fill-rate (%):\n" +
        "\n".join(f"    {c}: {non_null_pct[c]:.1f}%"
                  for c in non_null_pct.index if c in non_null_pct.index))

    # ------------------------------------------------------------------
    # Step 5: Train model
    # ------------------------------------------------------------------
    log("\n=== Step 5: Training model ===")
    model_pkg = train(feature_df)
    log(f"  Mode: {model_pkg['mode']}")
    if model_pkg.get("pr_auc") is not None:
        log(f"  PR-AUC: {model_pkg['pr_auc']:.4f}")

    # ------------------------------------------------------------------
    # Step 6: Save artifacts
    # ------------------------------------------------------------------
    log("\n=== Step 6: Saving artifacts ===")
    save_artifacts(model_pkg)
    log("  Done!")

    # ------------------------------------------------------------------
    # Quick smoke test
    # ------------------------------------------------------------------
    log("\n=== Quick smoke test ===")
    from src.model import predict_single
    test_cases = [
        ("CHINA",  "Semiconductor"),
        ("CANADA", "General"),
        ("EU",     "Automotive"),
        ("GLOBAL", "Steel & Aluminum"),
        ("INDIA",  "General"),
    ]
    for country, sector in test_cases:
        r = predict_single(country, sector, model_pkg)
        prob_str = (f", prob={r['tariff_risk_prob']:.3f}"
                    if r.get("tariff_risk_prob") is not None else "")
        log(f"  {country:25s} / {sector:20s} => score={r['tariff_risk_score']:.1f}{prob_str}")


if __name__ == "__main__":
    run_pipeline(verbose=True)

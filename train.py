"""
End-to-end Tariff Risk Forecasting pipeline — Sector-Only Edition.

Sector Model: predicts P(sector-specific tariff action in next 3 months)
              unit = (sector_std, month_start)

Label: y = 1 if any tariff event (First announced) falls in [month_start, month_start + 3 months).
Panel start: 2024-11-01 (data before this date is excluded from all datasets).

Usage:
    python train.py
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd

from src.data_loader import (
    load_gscpi,
    load_tariff_tracker,
)
from src.country_multiplier import compute_country_multipliers, save_country_multipliers
from src.panel import (
    build_sector_events,
    build_sector_panel,
    panel_stats,
    PANEL_START_DEFAULT,
    MASS_ROLLOUT_THRESHOLD,
)
from src.features import (
    build_sector_features,
    SECTOR_CAT_COLS,
)
from src.model import (
    train,
    save_artifacts,
    save_metrics,
    predict_sector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fill_rate_report(df: pd.DataFrame, feat_cols: list, label: str) -> list:
    present = [c for c in feat_cols if c in df.columns]
    fill = (df[present].notna().mean() * 100).round(1)
    print(f"\n  [{label}] Feature fill-rate:")
    for col, pct in fill.sort_values(ascending=False).items():
        flag = "  [LOW <20%]" if pct < 20.0 else ""
        print(f"    {col}: {pct:.1f}%{flag}")
    low = [c for c in present if fill.get(c, 0) < 20.0]
    return low


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

PANEL_START = PANEL_START_DEFAULT  # 2024-11-01


def run_pipeline(verbose: bool = True) -> None:
    def log(msg: str) -> None:
        if verbose:
            print(msg)

    os.makedirs("artifacts", exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Load raw data
    # ------------------------------------------------------------------
    log("\n=== Step 1: Loading raw data ===")

    log("  GSCPI...")
    gscpi_df = load_gscpi()
    gscpi_df = gscpi_df[gscpi_df["month"] >= PANEL_START].reset_index(drop=True)
    log(f"    => {len(gscpi_df):,} monthly obs ({gscpi_df['month'].min().date()} - {gscpi_df['month'].max().date()})")

    log("  tariff_tracker...")
    tariff_df = load_tariff_tracker()
    tariff_df = tariff_df[
        tariff_df["event_date"].notna() & (tariff_df["event_date"] >= PANEL_START)
    ].reset_index(drop=True)
    log(f"    => {len(tariff_df):,} actions (>= {PANEL_START.date()}) | "
        f"target_types: {dict(tariff_df['target_type'].value_counts())}")
    log(f"       sector_std: {dict(tariff_df['sector_std'].value_counts())}")
        # Country multipliers (policy-intensity proxy)
    country_mult = compute_country_multipliers(tariff_df)
    save_country_multipliers(country_mult, os.path.join("artifacts", "country_multipliers.json"))
    log(f"  country multipliers saved: {len(country_mult)} countries -> artifacts/country_multipliers.json")
    # ------------------------------------------------------------------
    # Step 2: Build tariff events
    # ------------------------------------------------------------------
    log("\n=== Step 2: Building tariff events ===")
    sector_events = build_sector_events(tariff_df)

    log(f"  Sector events: {len(sector_events)} unique (sector_std, event_date)")
    log(f"    mass-rollout flagged: {sector_events['is_mass_rollout'].sum()} "
        f"(threshold={MASS_ROLLOUT_THRESHOLD})")

    # ------------------------------------------------------------------
    # Step 3: Build monthly panels
    # ------------------------------------------------------------------
    log("\n=== Step 3: Building monthly panels ===")
    sector_panel = build_sector_panel(sector_events, feature_start=PANEL_START)
    log(f"  Sector panel: {sector_panel.shape}")
    log(f"    {panel_stats(sector_panel)}")

    # ------------------------------------------------------------------
    # Step 4: Feature engineering
    # ------------------------------------------------------------------
    log("\n=== Step 4: Feature engineering ===")
    log("  Building sector features (gscpi + history)...")
    sector_feat_df, sector_num_cols, _ = build_sector_features(
        sector_panel,
        sector_events,
        gscpi_df,
    )
    log(f"    => {sector_feat_df.shape} | {len(sector_num_cols)} numeric cols")

    # ------------------------------------------------------------------
    # Step 5: Fill-rate check
    # ------------------------------------------------------------------
    log("\n=== Step 5: Fill-rate check ===")
    s_low = _fill_rate_report(sector_feat_df, sector_num_cols, "Sector")
    if s_low:
        log(f"\n  Dropping {len(s_low)} sector feature(s) with <20% fill: {s_low}")
        sector_feat_df = sector_feat_df.drop(columns=s_low, errors="ignore")
        sector_num_cols = [c for c in sector_num_cols if c not in s_low]
    else:
        log("\n  All sector features above 20% fill threshold.")

    # ------------------------------------------------------------------
    # Step 6: Train model
    # ------------------------------------------------------------------
    log("\n=== Step 6: Training Sector Model ===")
    sector_pkg = train(
        sector_feat_df,
        feature_cols=sector_num_cols,
        cat_cols=SECTOR_CAT_COLS,
        model_label="sector",
    )
    log(f"  Mode: {sector_pkg['mode']}")
    if sector_pkg.get("fold_metrics"):
        log(f"  Walk-forward CV ({len(sector_pkg['fold_metrics'])} valid folds):")
        for fold in sector_pkg["fold_metrics"]:
            log(f"    train_end={fold['train_end']}  "
                f"val=[{fold['val_start']}..{fold['val_end']}]  "
                f"PR-AUC={fold['pr_auc']:.4f} (base={fold['baseline_pr_auc']:.4f})  "
                f"ROC-AUC={fold['roc_auc']:.4f}")
    if sector_pkg.get("pr_auc") is not None:
        log(f"  Mean PR-AUC:  {sector_pkg['pr_auc']:.4f}  "
            f"(baseline={sector_pkg['baseline_pr_auc']:.4f})")
        log(f"  Mean ROC-AUC: {sector_pkg['roc_auc']:.4f}")

    # ------------------------------------------------------------------
    # Step 7: Save artifacts
    # ------------------------------------------------------------------
    log("\n=== Step 7: Saving artifacts ===")
    save_artifacts(sector_pkg, model_type="sector")

    metrics = {
        "sector_model": {
            "mode":            sector_pkg["mode"],
            "n_positive":      sector_pkg["n_positive"],
            "n_total":         sector_pkg["n_total"],
            "baseline_pr_auc": sector_pkg["baseline_pr_auc"],
            "pr_auc":          sector_pkg.get("pr_auc"),
            "roc_auc":         sector_pkg.get("roc_auc"),
            "feature_cols":    sector_num_cols,
        }
    }
    save_metrics(metrics)
    log("  Done!")

    # ------------------------------------------------------------------
    # Step 8: Smoke test
    # ------------------------------------------------------------------
    log("\n=== Step 8: Smoke test ===")

    test_sectors = [
        "Automotive",
        "Steel & Aluminum",
        "Energy",
        "Maritime",
        "Aerospace",
    ]

    for sector in test_sectors:
        r = predict_sector(sector, sector_pkg)
        log(f"\n  {sector:20s}  score={r['tariff_risk_score']:6.1f}  "
            f"prob={r['tariff_risk_pct']:>6s}  [sector_only]")
        if r.get("top_drivers"):
            log("    Sector drivers:")
            for d in r["top_drivers"][:3]:
                log(f"      {d.get('feature','?'):40s}  "
                    f"val={d.get('value', d.get('importance','?'))}")


if __name__ == "__main__":
    run_pipeline(verbose=True)
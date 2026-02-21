"""
Model training, scoring, artifact persistence, and inference.

Honest-metrics CV changes:
- Skip walk-forward folds with tiny validation windows or too few positives/negatives.
  This prevents misleading PR-AUC/ROC-AUC spikes (e.g., 1.0 on a single-month val set).

Model choices:
- country: HistGradientBoostingClassifier (nonlinear, handles clustered events better)
- sector : LogisticRegression (works well on your dataset)

Calibration:
- CalibratedClassifierCV(method="sigmoid", cv=3) on the same dataset used to fit the final model.

Weighting:
- Combines panel sample_weight (mass-rollout downweight) and class-imbalance pos_weight.
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier

from .features import FEATURE_COLS, CAT_FEATURE_COLS

warnings.filterwarnings("ignore")

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")

# ---------------------------------------------------------------------------
# Training / CV thresholds
# ---------------------------------------------------------------------------
MIN_POS = 20

EMBARGO_MONTHS = 1
VAL_WINDOW_MONTHS = 3
MIN_TRAIN_MONTHS = 4

# Honest CV thresholds (NEW)
MIN_VAL_MONTHS = 2      # skip folds where validation spans < 2 months
MIN_VAL_POS = 5         # skip folds with < 5 positives in validation
MIN_VAL_NEG = 5         # skip folds with < 5 negatives in validation
MIN_TRAIN_POS = 10      # skip folds with < 10 positives in training

_HEURISTIC_WEIGHTS: dict[str, float] = {
    "trade_deficit":                    0.14,
    "trade_deficit_3m_change":          0.10,
    "gscpi":                            0.12,
    "tariff_count_country_12m":         0.18,
    "months_since_last_tariff_country": -0.15,
    "authority_count_12m_IEEPA":        0.12,
    "unrate":                           0.03,
    "month_of_year":                    0.00,
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _impute(X: pd.DataFrame, feature_cols: list, fill_values: dict) -> pd.DataFrame:
    X = X.copy()
    for col in feature_cols:
        if col in X.columns:
            fv = fill_values.get(col, X[col].median())
            X[col] = X[col].fillna(fv if pd.notna(fv) else 0.0)
    return X


def _compute_fill_values(X: pd.DataFrame, feature_cols: list) -> dict:
    return {col: float(X[col].median()) for col in feature_cols if col in X.columns}


def _safe_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y_true = np.asarray(y_true)
    if len(np.unique(y_true)) < 2:
        return 0.5
    return float(roc_auc_score(y_true, y_score))


def _score_to_prob(raw_score: float) -> float:
    return float(1.0 / (1.0 + np.exp(-raw_score)))


def _top_k_drivers(feature_names: list, feature_values: np.ndarray, weights: np.ndarray, k: int = 5) -> list:
    contributions = weights * feature_values
    idx = np.argsort(np.abs(contributions))[::-1][:k]
    return [
        {
            "feature":      feature_names[i],
            "value":        round(float(feature_values[i]), 4),
            "contribution": round(float(contributions[i]), 4),
        }
        for i in idx
        if np.abs(contributions[i]) > 1e-9
    ]


def _build_row_weights(feature_df: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """Combine sample_weight (mass-rollout) with pos_weight (class imbalance)."""
    n_pos = float(y.sum())
    n_neg = float((y == 0).sum())
    pos_weight = (n_neg / n_pos) if n_pos > 0 else 1.0

    base = feature_df["sample_weight"].values if "sample_weight" in feature_df.columns else np.ones(len(y))
    w = base.astype(float).copy()
    w[y.values == 1] *= pos_weight
    return w


def _make_model(model_label: str):
    """
    Choose model family:
    - country: HistGradientBoostingClassifier
    - sector:  LogisticRegression
    """
    if model_label == "country":
        return HistGradientBoostingClassifier(
            learning_rate=0.08,
            max_depth=3,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=0.1,
            early_stopping=True,
            random_state=42,
        ), "hgb"

    return LogisticRegression(
        max_iter=5000,
        class_weight=None,  # handled via sample weights
        random_state=42,
        C=0.5,
    ), "logreg"


# ---------------------------------------------------------------------------
# Walk-forward CV (metrics only)
# ---------------------------------------------------------------------------
def _walk_forward_cv(
    feature_df: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    num_cols: list,
    model_label: str,
) -> list:
    months_sorted = sorted(feature_df["month_start"].unique())
    n = len(months_sorted)
    fold_results: list[dict] = []

    for k in range(MIN_TRAIN_MONTHS, n):
        train_end = months_sorted[k - 1]
        val_start_idx = k + EMBARGO_MONTHS
        val_end_idx = val_start_idx + VAL_WINDOW_MONTHS

        if val_start_idx >= n:
            break

        val_months = months_sorted[val_start_idx:val_end_idx]
        if not val_months:
            break

        # HONEST METRICS: skip tiny validation windows
        if len(val_months) < MIN_VAL_MONTHS:
            continue

        tr_mask = feature_df["month_start"] <= train_end
        val_mask = feature_df["month_start"].isin(val_months)

        y_tr = y[tr_mask]
        y_val = y[val_mask]

        n_tr_pos = int(y_tr.sum())
        n_val_pos = int(y_val.sum())
        n_val_neg = int((y_val == 0).sum())

        # HONEST METRICS: skip folds with too little signal
        if n_tr_pos < MIN_TRAIN_POS:
            continue
        if n_val_pos < MIN_VAL_POS:
            continue
        if n_val_neg < MIN_VAL_NEG:
            continue

        model, kind = _make_model(model_label)
        w_tr = _build_row_weights(feature_df.loc[tr_mask], y_tr)

        if kind == "logreg":
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X.loc[tr_mask, num_cols].values)
            X_va = scaler.transform(X.loc[val_mask, num_cols].values)
            model.fit(X_tr, y_tr.values, sample_weight=w_tr)
            proba = model.predict_proba(X_va)[:, 1]
        else:
            X_tr = X.loc[tr_mask, num_cols].values
            X_va = X.loc[val_mask, num_cols].values
            model.fit(X_tr, y_tr.values, sample_weight=w_tr)
            proba = model.predict_proba(X_va)[:, 1]

        pr_auc = float(average_precision_score(y_val.values, proba))
        base = float(y_val.mean())
        roc = _safe_roc_auc(y_val.values, proba)

        fold_results.append({
            "train_end": str(train_end.date()),
            "val_start": str(val_months[0].date()),
            "val_end": str(val_months[-1].date()),
            "n_train": int(tr_mask.sum()),
            "n_val": int(val_mask.sum()),
            "n_pos_train": n_tr_pos,
            "n_pos_val": n_val_pos,
            "n_neg_val": n_val_neg,
            "pr_auc": round(pr_auc, 4),
            "roc_auc": round(roc, 4),
            "baseline_pr_auc": round(base, 4),
        })

    return fold_results


# ---------------------------------------------------------------------------
# Core training
# ---------------------------------------------------------------------------
def train(
    feature_df: pd.DataFrame,
    feature_cols: list | None = None,
    cat_cols: list | None = None,
    model_label: str = "model",
) -> dict:
    if feature_cols is None:
        feature_cols = FEATURE_COLS
    if cat_cols is None:
        cat_cols = CAT_FEATURE_COLS

    all_cols = [c for c in (cat_cols + feature_cols) if c in feature_df.columns]
    X_full = feature_df[all_cols].copy()
    y_full = feature_df["y"].copy()

    n_pos = int(y_full.sum())
    n_total = len(y_full)
    baseline = round(n_pos / n_total, 4) if n_total else 0.0

    print(f"[train:{model_label}] +{n_pos}/{n_total} (pos_rate={baseline:.4f}, baseline_PR-AUC={baseline:.4f})")

    fill_values = _compute_fill_values(X_full, feature_cols)
    X_full = _impute(X_full, feature_cols, fill_values)
    num_cols = [c for c in feature_cols if c in X_full.columns]

    # fallback
    if n_pos < MIN_POS:
        print(f"[train:{model_label}] Only {n_pos} positives (<{MIN_POS}) -> risk_score fallback")
        scaler = StandardScaler()
        X_num = scaler.fit_transform(X_full[num_cols].values)
        weights = None

        w_all = _build_row_weights(feature_df, y_full)
        try:
            lr = LogisticRegression(max_iter=5000, random_state=42, C=0.2)
            lr.fit(X_num, y_full.values, sample_weight=w_all)
            coef = lr.coef_[0]
            weights = {num_cols[i]: float(coef[i]) for i in range(len(num_cols))}
        except Exception:
            pass

        return {
            "mode": "risk_score",
            "model": None,
            "scaler": scaler,
            "num_cols": num_cols,
            "all_cols": list(X_full.columns),
            "cat_cols": cat_cols,
            "feature_cols": feature_cols,
            "fill_values": fill_values,
            "fit_on_scaled_num": True,
            "pr_auc": None,
            "roc_auc": None,
            "baseline_pr_auc": baseline,
            "n_positive": n_pos,
            "n_total": n_total,
            "weights": weights,
            "fold_metrics": [],
            "feature_panel": feature_df.copy(),
            "model_label": model_label,
        }

    # CV metrics
    print(f"[train:{model_label}] Walk-forward CV ...")
    fold_metrics = _walk_forward_cv(feature_df, X_full, y_full, num_cols, model_label)

    if fold_metrics:
        mean_pr = round(float(np.mean([f["pr_auc"] for f in fold_metrics])), 4)
        mean_roc = round(float(np.mean([f["roc_auc"] for f in fold_metrics])), 4)
        print(f"[train:{model_label}] CV MEAN PR-AUC={mean_pr:.4f} ROC-AUC={mean_roc:.4f} ({len(fold_metrics)} folds)")
    else:
        mean_pr = None
        mean_roc = None
        print(f"[train:{model_label}] CV: no valid folds (after honest-metrics filtering)")

    # Final fit on ALL rows (hackathon mode)
    model, kind = _make_model(model_label)
    w_all = _build_row_weights(feature_df, y_full)

    scaler = None
    if kind == "logreg":
        scaler = StandardScaler()
        X_all = scaler.fit_transform(X_full[num_cols].values)
        model.fit(X_all, y_full.values, sample_weight=w_all)
        calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=3)
        calibrated.fit(X_all, y_full.values, sample_weight=w_all)
        fit_on_scaled = True

        coef = getattr(model, "coef_", None)
        feat_imps = {}
        if coef is not None:
            feat_imps = dict(zip(num_cols, np.abs(coef[0]).tolist()))
    else:
        X_all = X_full[num_cols].values
        model.fit(X_all, y_full.values, sample_weight=w_all)
        calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=3)
        calibrated.fit(X_all, y_full.values, sample_weight=w_all)
        fit_on_scaled = False
        feat_imps = {}

    print(f"[train:{model_label}] Final fit done. Calibration=cv3 sigmoid. kind={kind}")

    return {
        "mode": "probability",
        "model": calibrated,
        "scaler": scaler,
        "num_cols": num_cols,
        "all_cols": list(X_full.columns),
        "cat_cols": cat_cols,
        "feature_cols": feature_cols,
        "fill_values": fill_values,
        "fit_on_scaled_num": fit_on_scaled,
        "pr_auc": mean_pr,
        "roc_auc": mean_roc,
        "baseline_pr_auc": baseline,
        "n_positive": n_pos,
        "n_total": n_total,
        "weights": None,
        "feat_importances": feat_imps,
        "fold_metrics": fold_metrics,
        "feature_panel": feature_df.copy(),
        "model_label": model_label,
    }


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------
def _predict_from_pkg(entity: str, key_col: str, pkg: dict) -> dict:
    panel = pkg["feature_panel"]
    fill_values = pkg["fill_values"]
    num_cols = pkg["num_cols"]
    feature_cols = pkg.get("feature_cols", FEATURE_COLS)
    cat_cols = pkg.get("cat_cols", CAT_FEATURE_COLS)
    mode = pkg["mode"]

    entity_norm = str(entity).strip()
    series = panel[key_col].astype(str).str.strip()
    mask = series.str.casefold() == entity_norm.casefold()
    sub = panel[mask]

    if sub.empty:
        row_df = pd.DataFrame([{c: np.nan for c in feature_cols + cat_cols}])
        row_df[key_col] = entity_norm
        as_of = "n/a"
    else:
        latest = sub["month_start"].max()
        row_df = sub[sub["month_start"] == latest].head(1).copy()
        as_of = str(latest.date())

    row_df = _impute(row_df, feature_cols, fill_values)
    x_num = row_df[num_cols].values[0] if num_cols else np.array([])

    result = {"mode": mode, "entity": entity_norm, "key_col": key_col, "as_of_month": as_of}

    if mode == "probability" and pkg["model"] is not None:
        model = pkg["model"]
        if pkg.get("fit_on_scaled_num", False):
            scaler = pkg["scaler"]
            x_scaled = scaler.transform(x_num.reshape(1, -1))
            proba = float(model.predict_proba(x_scaled)[:, 1][0])
        else:
            proba = float(model.predict_proba(x_num.reshape(1, -1))[:, 1][0])

        result["tariff_risk_prob"] = round(proba, 4)
        result["tariff_risk_score"] = round(proba * 100, 2)
        result["tariff_risk_pct"] = f"{round(proba * 100, 1)}%"

        imps = pkg.get("feat_importances") or {}
        if imps:
            top = sorted(imps.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
            result["top_drivers"] = [{"feature": f, "importance": round(v, 4)} for f, v in top]
        else:
            vals = x_num
            idx = np.argsort(np.abs(vals))[::-1][:5]
            result["top_drivers"] = [{"feature": num_cols[i], "importance": round(float(vals[i]), 4)} for i in idx]

        return result

    hw = pkg.get("weights") or _HEURISTIC_WEIGHTS
    w_arr = np.array([hw.get(c, 0.0) for c in num_cols])
    raw = float(np.dot(w_arr, x_num))
    proba = _score_to_prob(raw)

    result["tariff_risk_prob"] = round(proba, 4)
    result["tariff_risk_score"] = round(proba * 100, 2)
    result["tariff_risk_pct"] = f"{round(proba * 100, 1)}%"
    result["top_drivers"] = _top_k_drivers(num_cols, x_num, w_arr)
    return result


def predict_blended(country: str, sector: str, country_pkg: dict, sector_pkg: dict | None = None) -> dict:
    country_norm = str(country).strip().upper()
    sector_norm = str(sector).strip()

    c_res = _predict_from_pkg(country_norm, "country_std", country_pkg)

    if sector_pkg is None or sector_norm.casefold() == "general":
        prob = float(c_res.get("tariff_risk_prob", 0.0) or 0.0)
        return {
            "country": country_norm,
            "sector": sector_norm,
            "tariff_risk_prob": prob,
            "tariff_risk_score": round(prob * 100, 2),
            "tariff_risk_pct": f"{round(prob * 100, 1)}%",
            "as_of_month": c_res.get("as_of_month"),
            "blend_mode": "country_only",
            "country_model": c_res,
        }

    s_res = _predict_from_pkg(sector_norm, "sector_std", sector_pkg)
    prob_c = float(c_res.get("tariff_risk_prob", 0.0) or 0.0)
    prob_s = float(s_res.get("tariff_risk_prob", 0.0) or 0.0)

    blended = round(0.6 * prob_c + 0.4 * prob_s, 4)

    return {
        "country": country_norm,
        "sector": sector_norm,
        "tariff_risk_prob": blended,
        "tariff_risk_score": round(blended * 100, 2),
        "tariff_risk_pct": f"{round(blended * 100, 1)}%",
        "as_of_month": c_res.get("as_of_month"),
        "blend_mode": "0.6_country_0.4_sector",
        "country_model": {"prob": round(prob_c, 4), "pct": f"{round(prob_c * 100, 1)}%", "top_drivers": c_res.get("top_drivers")},
        "sector_model": {"prob": round(prob_s, 4), "pct": f"{round(prob_s * 100, 1)}%", "top_drivers": s_res.get("top_drivers")},
    }

def predict_sector(sector: str, sector_pkg: dict) -> dict:
    """
    Sector-only inference.
    Returns calibrated probability and formatted percent for a given sector_std.
    """
    return _predict_from_pkg(str(sector).strip(), "sector_std", sector_pkg)

# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------
def save_artifacts(model_pkg: dict, model_type: str = "country", out_dir: str = ARTIFACTS_DIR) -> None:
    os.makedirs(out_dir, exist_ok=True)
    suffix = model_type

    joblib.dump(model_pkg["model"], os.path.join(out_dir, f"model_{suffix}.pkl"))
    joblib.dump(model_pkg["scaler"], os.path.join(out_dir, f"scaler_{suffix}.pkl"))

    model_pkg["feature_panel"].to_csv(os.path.join(out_dir, f"feature_panel_{suffix}.csv"), index=False)

    schema = {k: v for k, v in model_pkg.items() if k not in ("model", "scaler", "feature_panel")}
    with open(os.path.join(out_dir, f"feature_schema_{suffix}.json"), "w") as f:
        json.dump(schema, f, default=str, indent=2)

    print(f"[save_artifacts] {suffix} artifacts -> {out_dir}")


def save_metrics(metrics: dict, out_dir: str = ARTIFACTS_DIR) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, default=str, indent=2)
    print(f"[save_metrics] metrics.json -> {out_dir}")
    
def _clamp01(x: float, hi: float = 0.99) -> float:
    return float(max(0.0, min(hi, x)))

def apply_country_multiplier(prob: float, country: str, multipliers: dict) -> tuple[float, float]:
    """
    Returns (scaled_prob, multiplier_used)
    """
    if multipliers is None:
        return prob, 1.0
    key = str(country).strip().upper()
    m = float(multipliers.get(key, 1.0))
    return _clamp01(prob * m), m

def predict_sector_scaled(
    country: str,
    sector: str,
    sector_pkg: dict,
    country_multipliers: dict,
) -> dict:
    """
    Sector probability scaled by a country multiplier in [0.5, 2.0].
    """
    s_res = _predict_from_pkg(str(sector).strip(), "sector_std", sector_pkg)
    p = float(s_res.get("tariff_risk_prob", 0.0))
    p2, m = apply_country_multiplier(p, country, country_multipliers)

    return {
        "country": country,
        "sector": sector,
        "base_sector_prob": round(p, 4),
        "country_multiplier": round(m, 4),
        "tariff_risk_prob": round(p2, 4),
        "tariff_risk_score": round(p2 * 100, 2),
        "tariff_risk_pct": f"{round(p2 * 100, 1)}%",
        "sector_model": s_res,
    }
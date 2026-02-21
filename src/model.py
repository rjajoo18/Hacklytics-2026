"""
Model training, scoring, artifact persistence, and single-row prediction.

Decision path:
  ┌─ n_positive >= 50 → CatBoostClassifier (time-based split, PR-AUC eval,
  │                      probability output, calibrated)
  └─ else
       ├─ 1 <= n_positive < 50 → RegularisedLogisticRegression
       │                          coefficients become heuristic weights
       └─ n_positive == 0 → pure heuristic scoring

Output for every path:
  {mode, tariff_risk_score (0-100), tariff_risk_prob (if supervised),
   top_drivers}
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.calibration import CalibratedClassifierCV

from .features import FEATURE_COLS, CAT_FEATURE_COLS, get_feature_matrix

warnings.filterwarnings("ignore")

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")

# Heuristic feature weights (applied to standardised values).
# Signs are chosen so that "more risky" → higher score.
_HEURISTIC_WEIGHTS: dict[str, float] = {
    "pol_risk_3m_change":      0.28,   # rising risk score → more likely tariff
    "pol_risk_score":          0.18,   # currently high risk
    "trade_deficit":           0.14,   # large US deficit → target for tariffs
    "trade_deficit_3m_change": 0.10,   # growing deficit
    "gscpi":                   0.12,   # supply-chain stress
    "fx_3m_std":               0.08,   # FX volatility
    "gscpi_3m_mean":           0.05,
    "unrate":                  0.03,   # US unemployment (macro context)
    "manuf_M_T":               0.02,
    "month_of_year":           0.00,   # minimal direct effect
}

MIN_SUPERVISED = 50   # switch threshold


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _impute(X: pd.DataFrame, fill_values: dict | None = None) -> pd.DataFrame:
    """Fill NaNs: use provided fill_values dict or column medians."""
    X = X.copy()
    num_cols = [c for c in FEATURE_COLS if c in X.columns]
    for col in num_cols:
        fv = (fill_values or {}).get(col, X[col].median())
        X[col] = X[col].fillna(fv if pd.notna(fv) else 0.0)
    for col in CAT_FEATURE_COLS:
        if col in X.columns:
            X[col] = X[col].fillna("UNKNOWN").astype(str)
    return X


def _compute_fill_values(X: pd.DataFrame) -> dict:
    return {col: float(X[col].median()) for col in FEATURE_COLS if col in X.columns}


def _score_to_prob(raw_score: float) -> float:
    """Sigmoid mapping of raw heuristic score → [0, 1]."""
    return float(1.0 / (1.0 + np.exp(-raw_score)))


def _top_k_drivers(
    feature_names: list[str],
    feature_values: np.ndarray,
    weights: np.ndarray,
    k: int = 5,
) -> list[dict]:
    contributions = weights * feature_values
    idx = np.argsort(np.abs(contributions))[::-1][:k]
    return [
        {
            "feature": feature_names[i],
            "value": round(float(feature_values[i]), 4),
            "contribution": round(float(contributions[i]), 4),
        }
        for i in idx
        if np.abs(contributions[i]) > 1e-9
    ]


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(feature_df: pd.DataFrame) -> dict:
    """
    Train a model on the labelled feature panel.

    Parameters
    ----------
    feature_df : full panel with FEATURE_COLS, CAT_FEATURE_COLS, 'y', 'month_start'

    Returns
    -------
    model_pkg : dict containing all artifacts needed for prediction
    """
    X_full, y_full = get_feature_matrix(feature_df)
    n_pos = int(y_full.sum())
    print(f"[train] Positive labels: {n_pos} / {len(y_full)}")

    fill_values = _compute_fill_values(X_full)
    X_full = _impute(X_full, fill_values)

    num_cols = [c for c in FEATURE_COLS if c in X_full.columns]

    # ----------------------------------------------------------------
    # Path A: Supervised (CatBoost or LogReg)
    # ----------------------------------------------------------------
    if n_pos >= MIN_SUPERVISED:
        # Time-based split: last 20% of months → test
        months_sorted = sorted(feature_df["month_start"].unique())
        cutoff = months_sorted[int(len(months_sorted) * 0.8)]
        train_mask = feature_df["month_start"] < cutoff
        test_mask  = feature_df["month_start"] >= cutoff

        X_tr, y_tr = X_full[train_mask], y_full[train_mask]
        X_te, y_te = X_full[test_mask],  y_full[test_mask]

        scaler = StandardScaler()
        X_tr_num = scaler.fit_transform(X_tr[num_cols].values)
        X_te_num = scaler.transform(X_te[num_cols].values)

        # Scale ratio for class imbalance
        scale_pos = max(1, int((y_tr == 0).sum() / max(1, (y_tr == 1).sum())))

        try:
            from catboost import CatBoostClassifier

            cat_idx = [list(X_full.columns).index(c)
                       for c in CAT_FEATURE_COLS if c in X_full.columns]

            model = CatBoostClassifier(
                iterations=400,
                learning_rate=0.05,
                depth=6,
                loss_function="Logloss",
                eval_metric="AUC",
                scale_pos_weight=scale_pos,
                random_seed=42,
                verbose=0,
                allow_writing_files=False,
            )
            model.fit(
                X_tr, y_tr,
                cat_features=cat_idx,
                eval_set=(X_te, y_te),
                early_stopping_rounds=40,
            )
            proba_te = model.predict_proba(X_te)[:, 1]
            pr_auc = average_precision_score(y_te, proba_te)
            print(f"[train] CatBoost  PR-AUC = {pr_auc:.4f}")
            mode = "probability"
            weights = None   # use SHAP from CatBoost
            feat_importances = dict(zip(
                list(X_full.columns),
                model.get_feature_importance().tolist()
            ))

        except ImportError:
            print("[train] catboost not found — falling back to LogisticRegression")
            model = LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced",
                                       random_state=42)
            model.fit(X_tr_num, y_tr.values)
            proba_te = model.predict_proba(X_te_num)[:, 1]
            pr_auc = average_precision_score(y_te, proba_te)
            print(f"[train] LogReg  PR-AUC = {pr_auc:.4f}")
            mode = "probability"
            weights = model.coef_[0]
            feat_importances = dict(zip(num_cols, np.abs(weights).tolist()))

        return {
            "mode": mode,
            "model": model,
            "scaler": scaler,
            "num_cols": num_cols,
            "all_cols": list(X_full.columns),
            "cat_feature_cols": CAT_FEATURE_COLS,
            "fill_values": fill_values,
            "pr_auc": pr_auc,
            "n_positive": n_pos,
            "weights": weights,
            "feat_importances": feat_importances,
            "heuristic_weights": _HEURISTIC_WEIGHTS,
            "feature_panel": feature_df.copy(),
        }

    # ----------------------------------------------------------------
    # Path B: Risk Score (LogReg with few labels OR pure heuristic)
    # ----------------------------------------------------------------
    scaler = StandardScaler()
    X_num = scaler.fit_transform(X_full[num_cols].values)

    if n_pos >= 1:
        logreg = LogisticRegression(C=0.05, max_iter=2000, class_weight="balanced",
                                    random_state=42)
        try:
            logreg.fit(X_num, y_full.values)
            coef = logreg.coef_[0]
            # Build weights dict from significant coefficients
            weights = {num_cols[i]: float(coef[i]) for i in range(len(num_cols))}
            print(f"[train] LogReg risk-score mode (n_pos={n_pos}), using coef as weights")
        except Exception as e:
            print(f"[train] LogReg failed ({e}), using heuristic weights")
            weights = None
    else:
        weights = None
        print("[train] No positive labels — pure heuristic scoring")

    return {
        "mode": "risk_score",
        "model": None,
        "scaler": scaler,
        "num_cols": num_cols,
        "all_cols": list(X_full.columns),
        "cat_feature_cols": CAT_FEATURE_COLS,
        "fill_values": fill_values,
        "pr_auc": None,
        "n_positive": n_pos,
        "weights": weights,
        "feat_importances": None,
        "heuristic_weights": _HEURISTIC_WEIGHTS,
        "feature_panel": feature_df.copy(),
    }


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict_single(country: str, sector: str, model_pkg: dict) -> dict:
    """
    Predict tariff risk for a (country, sector) pair using the latest available
    feature row in the saved feature panel.

    Returns
    -------
    dict with keys: mode, tariff_risk_score, tariff_risk_prob (optional),
                    top_drivers, country, sector, as_of_month
    """
    panel: pd.DataFrame = model_pkg["feature_panel"]
    fill_values: dict    = model_pkg["fill_values"]
    num_cols: list[str]  = model_pkg["num_cols"]
    mode: str            = model_pkg["mode"]

    # Look for exact match, then country-only fallback
    mask = (panel["country"] == country) & (panel["sector"] == sector)
    sub = panel[mask]
    if sub.empty:
        # Fallback: use most-recent row for the country with any sector
        mask_c = panel["country"] == country
        sub = panel[mask_c]
    if sub.empty:
        # No data at all — build a zero row
        row_df = pd.DataFrame([{c: np.nan for c in FEATURE_COLS + CAT_FEATURE_COLS}])
        row_df["country"] = country
        row_df["sector"]  = sector
        as_of = "n/a"
    else:
        # Take the most recent month
        latest_month = sub["month_start"].max()
        row_df = sub[sub["month_start"] == latest_month].head(1).copy()
        as_of = str(latest_month.date())

    row_df = _impute(row_df, fill_values)
    X_row = row_df[[c for c in FEATURE_COLS if c in row_df.columns]]
    x_num = X_row[num_cols].values[0] if num_cols else np.array([])

    # Scale
    scaler: StandardScaler = model_pkg["scaler"]
    try:
        x_scaled = scaler.transform(x_num.reshape(1, -1))[0]
    except Exception:
        x_scaled = x_num

    # ----------------------------------------------------------------
    # Compute score / probability
    # ----------------------------------------------------------------
    result: dict = {"mode": mode, "country": country, "sector": sector,
                    "as_of_month": as_of}

    if mode == "probability" and model_pkg["model"] is not None:
        model = model_pkg["model"]
        try:
            # CatBoost can accept the full row (with cat features)
            full_row = row_df[[c for c in model_pkg["all_cols"] if c in row_df.columns]]
            proba = float(model.predict_proba(full_row)[:, 1][0])
        except Exception:
            # Fallback for LogReg
            proba = float(model_pkg["model"].predict_proba(x_scaled.reshape(1, -1))[:, 1][0])

        risk_score = round(proba * 100, 2)
        result["tariff_risk_prob"] = round(proba, 4)
        result["tariff_risk_score"] = risk_score

        # Top drivers via feature importance (fallback)
        importances = model_pkg.get("feat_importances") or {}
        top_features = sorted(importances.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        result["top_drivers"] = [
            {"feature": f, "importance": round(v, 4)} for f, v in top_features
        ]

    else:
        # Risk score path
        hw = model_pkg["weights"] or _HEURISTIC_WEIGHTS
        w_arr = np.array([hw.get(c, 0.0) for c in num_cols])
        raw_score = float(np.dot(w_arr, x_scaled))
        proba = _score_to_prob(raw_score)
        risk_score = round(proba * 100, 2)

        result["tariff_risk_score"] = risk_score
        if mode == "risk_score":
            result["tariff_risk_prob"] = None

        result["top_drivers"] = _top_k_drivers(num_cols, x_scaled, w_arr, k=5)

    return result


# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------

def save_artifacts(model_pkg: dict, out_dir: str = ARTIFACTS_DIR) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # Model + scaler
    joblib.dump(model_pkg["model"],  os.path.join(out_dir, "model.pkl"))
    joblib.dump(model_pkg["scaler"], os.path.join(out_dir, "scaler.pkl"))

    # Feature panel (for lookup)
    panel = model_pkg["feature_panel"]
    panel.to_csv(os.path.join(out_dir, "feature_panel.csv"), index=False)

    # Metadata
    meta = {k: v for k, v in model_pkg.items()
            if k not in ("model", "scaler", "feature_panel")}
    # Convert ndarray to list for JSON
    if meta.get("weights") is not None and not isinstance(meta["weights"], dict):
        meta["weights"] = meta["weights"].tolist()
    with open(os.path.join(out_dir, "model_meta.json"), "w") as f:
        json.dump(meta, f, default=str, indent=2)

    print(f"[save_artifacts] Artifacts saved to: {out_dir}")


def load_artifacts(out_dir: str = ARTIFACTS_DIR) -> dict:
    model  = joblib.load(os.path.join(out_dir, "model.pkl"))
    scaler = joblib.load(os.path.join(out_dir, "scaler.pkl"))
    panel  = pd.read_csv(os.path.join(out_dir, "feature_panel.csv"),
                         parse_dates=["month_start"])
    with open(os.path.join(out_dir, "model_meta.json")) as f:
        meta = json.load(f)

    # Restore weights as dict if it was saved as list
    if isinstance(meta.get("weights"), list):
        meta["weights"] = {meta["num_cols"][i]: meta["weights"][i]
                           for i in range(len(meta["weights"]))}

    meta["model"]          = model
    meta["scaler"]         = scaler
    meta["feature_panel"]  = panel
    return meta

"""
FinSight AI — ML Training Pipeline

data → features → (per horizon) target → purged split → train every model →
evaluate on validation + test → pick best (lowest validation RMSE) → save
artifacts + metadata.json (the model registry used by the prediction service).

Runs synchronously; the API executes it in a worker thread (see app/ml/jobs.py).
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from app.config import settings
from app.data import market_data as md
from app.ml.evaluation import evaluate_model, select_best_model
from app.ml.feature_engineering import FEATURE_COLUMNS, MIN_ROWS, compute_features, create_target, time_series_split
from app.ml.models import MODEL_REGISTRY, model_availability

logger = logging.getLogger("finsight.ml.pipeline")

HORIZONS = [1, 5, 10, 30]  # trading days
BACKTEST_HORIZONS = {1, 5}  # store test-set predictions for charting

ProgressCallback = Callable[[float, str], None]


def symbol_dir(symbol: str) -> str:
    return os.path.join(settings.model_storage_path, symbol.upper().replace("^", "_"))


def load_metadata(symbol: str) -> Optional[dict]:
    path = os.path.join(symbol_dir(symbol), "metadata.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _clean(obj):
    """Make numpy/pandas values JSON serialisable."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if np.isnan(obj) or np.isinf(obj) else round(float(obj), 6)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


class TrainingPipeline:
    def __init__(self, symbol: str, model_types: Optional[List[str]] = None, lookback_years: int = 5,
                 horizons: Optional[List[int]] = None, progress: Optional[ProgressCallback] = None):
        self.symbol = symbol.upper()
        self.model_types = [m for m in (model_types or list(MODEL_REGISTRY)) if m in MODEL_REGISTRY]
        self.lookback_years = max(2, min(int(lookback_years), 10))
        self.horizons = horizons or HORIZONS
        self.storage_dir = symbol_dir(self.symbol)
        self._progress = progress or (lambda p, m: None)

    def load_data(self):
        # Yahoo only accepts 1y/2y/5y/10y periods: download the next valid period and trim.
        period = "2y" if self.lookback_years <= 2 else "5y" if self.lookback_years <= 5 else "10y"
        df, is_demo = md.history(self.symbol, period, "1d")
        if df.empty:
            raise ValueError(f"No price history returned for {self.symbol}")
        cutoff = df.index[-1] - pd.DateOffset(years=self.lookback_years)
        df = df[df.index >= cutoff]
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna(), is_demo

    def run(self) -> Dict:
        started = time.time()
        self._progress(0.02, "Downloading price history")
        raw, is_demo = self.load_data()
        feature_df = compute_features(raw)
        if len(feature_df) < MIN_ROWS:
            raise ValueError(f"Only {len(feature_df)} usable rows after feature engineering; need {MIN_ROWS}+ (try a longer lookback)")

        availability = model_availability()
        skipped = {m: availability[m] for m in self.model_types if availability.get(m)}
        models = [m for m in self.model_types if m not in skipped]
        if not models:
            raise ValueError("No model types are available to train")

        total_steps = len(self.horizons) * len(models)
        step = 0
        horizons_out: Dict[str, dict] = {}
        importances: Dict[str, dict] = {}

        for h in self.horizons:
            X_all, y_all = create_target(feature_df, horizon=h)
            X_feat = X_all[FEATURE_COLUMNS]
            base_close = X_all["Close"]
            try:
                X_tr, X_va, X_te, y_tr, y_va, y_te = time_series_split(X_feat, y_all, gap=h)
            except ValueError:
                step += len(models)
                continue
            if len(X_tr) < 150:
                step += len(models)
                continue

            def to_price(idx, returns):
                return base_close.loc[idx].values * (1 + np.asarray(returns))

            actual_val, actual_test = to_price(X_va.index, y_va), to_price(X_te.index, y_te)
            h_models: Dict[str, dict] = {}
            backtest_preds: Dict[str, list] = {}

            for name in models:
                step += 1
                self._progress(0.05 + 0.9 * (step - 1) / total_steps, f"Training {name.replace('_', ' ')} · {h}-day horizon")
                t0 = time.time()
                try:
                    model = MODEL_REGISTRY[name](symbol=self.symbol, horizon=h)
                    model.fit(X_tr, y_tr, X_va, y_va)
                    preds = pd.Series(model.predict_full(X_feat), index=X_feat.index)
                    pv, pt = preds.loc[X_va.index].values, preds.loc[X_te.index].values

                    val_m = evaluate_model(actual_val, to_price(X_va.index, pv), "validation", base_close.loc[X_va.index].values)
                    test_m = evaluate_model(actual_test, to_price(X_te.index, pt), "test", base_close.loc[X_te.index].values)
                    resid = y_va.values - pv
                    path = model.save(os.path.join(self.storage_dir, f"h{h}"))

                    h_models[name] = {
                        "display_name": model.display_name,
                        "validation": val_m,
                        "test": test_m,
                        "resid_std": float(np.nanstd(resid)),
                        "hyperparameters": model.hyperparameters,
                        "artifact": os.path.relpath(path, settings.model_storage_path),
                        "train_seconds": round(time.time() - t0, 2),
                    }
                    if h in BACKTEST_HORIZONS:
                        backtest_preds[name] = to_price(X_te.index, pt).round(2).tolist()
                    if h == 1:
                        imp = model.feature_importances()
                        if imp:
                            importances[name] = dict(sorted(imp.items(), key=lambda kv: -kv[1])[:12])
                except Exception as exc:  # one failing model must not stop the others
                    logger.exception("Training %s h=%s failed", name, h)
                    h_models[name] = {"error": str(exc)}

            ok = {k: v["validation"] for k, v in h_models.items() if "error" not in v}
            horizons_out[str(h)] = {
                "best_model": select_best_model(ok) if ok else None,
                "split": {
                    "train": {"start": str(X_tr.index[0].date()), "end": str(X_tr.index[-1].date()), "rows": len(X_tr)},
                    "validation": {"start": str(X_va.index[0].date()), "end": str(X_va.index[-1].date()), "rows": len(X_va)},
                    "test": {"start": str(X_te.index[0].date()), "end": str(X_te.index[-1].date()), "rows": len(X_te)},
                    "purge_gap_rows": h,
                },
                "models": h_models,
                "naive_baseline": {
                    **evaluate_model(actual_test, base_close.loc[X_te.index].values, "test", base_close.loc[X_te.index].values),
                    "directional_accuracy": None,  # a "no change" forecast makes no up/down call
                },
            }
            if h in BACKTEST_HORIZONS and backtest_preds:
                target_dates = [str((d + pd.offsets.BDay(h)).date()) for d in X_te.index]
                horizons_out[str(h)]["backtest"] = {
                    "dates": target_dates,
                    "actual": np.round(actual_test, 2).tolist(),
                    "predictions": backtest_preds,
                }

        if not horizons_out:
            raise ValueError("Not enough data to train any horizon")

        metadata = _clean({
            "symbol": self.symbol,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "data_source": "simulated" if is_demo else "yahoo_finance",
            "is_demo": is_demo,
            "lookback_years": self.lookback_years,
            "data_range": {"start": str(raw.index[0].date()), "end": str(raw.index[-1].date()), "rows": len(raw)},
            "feature_rows": len(feature_df),
            "feature_columns": FEATURE_COLUMNS,
            "target": "forward h-day return, converted to price",
            "models_trained": models,
            "models_skipped": skipped,
            "horizons": horizons_out,
            "feature_importance": importances,
            "training_seconds": round(time.time() - started, 1),
        })
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(os.path.join(self.storage_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        self._progress(1.0, "Training complete")
        return metadata

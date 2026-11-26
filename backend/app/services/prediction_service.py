"""
FinSight AI — Prediction Service
Loads trained models from the registry (metadata.json + artifacts) and produces
multi-horizon forecasts with 95% prediction intervals.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.data import market_data as md
from app.data.providers.demo_provider import DemoDataProvider
from app.ml.feature_engineering import FEATURE_COLUMNS, compute_features
from app.ml.models import MODEL_REGISTRY, model_availability
from app.ml.pipeline import HORIZONS, load_metadata, symbol_dir
from app.utils.cache import cache_get, cache_set

Z_95 = 1.96


def _forecast(symbol: str, metadata: dict) -> Optional[dict]:
    """Synchronous: compute features on the latest data and run every saved model."""
    if metadata.get("is_demo"):
        df = DemoDataProvider.history(symbol, "2y", "1d")
    else:
        try:
            df, _ = md.history(symbol, "2y", "1d")
        except md.MarketDataError:
            return None
    if df.empty:
        return None

    features = compute_features(df[["Open", "High", "Low", "Close", "Volume"]].dropna())
    if features.empty:
        return None
    X = features[FEATURE_COLUMNS]
    last_close = float(features["Close"].iloc[-1])
    last_date = features.index[-1]
    available = model_availability()

    predictions: Dict[str, dict] = {}
    for h_str, hdata in metadata.get("horizons", {}).items():
        h = int(h_str)
        directory = os.path.join(symbol_dir(symbol), f"h{h}")
        target_date = (last_date + pd.offsets.BDay(h)).date()
        for name, info in hdata.get("models", {}).items():
            if "error" in info or available.get(name):
                continue
            try:
                model = MODEL_REGISTRY[name].load(directory, symbol, h)
                window = X.tail(max(60, getattr(model, "sequence_length", 1)))
                pred_return = float(model.predict_full(window)[-1])
            except Exception:
                continue
            if np.isnan(pred_return):
                continue
            band = Z_95 * float(info.get("resid_std") or 0)
            predicted = last_close * (1 + pred_return)
            predictions.setdefault(name, {})[f"{h}d"] = {
                "horizon_days": h,
                "target_date": str(target_date),
                "predicted_price": round(predicted, 2),
                "lower_bound": round(last_close * (1 + pred_return - band), 2),
                "upper_bound": round(last_close * (1 + pred_return + band), 2),
                "predicted_change_pct": round(pred_return * 100, 2),
                "current_price": round(last_close, 2),
                "test_directional_accuracy": info["test"].get("directional_accuracy"),
                "test_mape": info["test"].get("mape"),
                "is_best": hdata.get("best_model") == name,
            }

    historical = [
        {"date": str(ts.date()), "close": round(float(row["Close"]), 2)}
        for ts, row in df.tail(120).iterrows()
    ]
    return {"predictions": predictions, "historical": historical, "last_close": last_close, "as_of": str(last_date.date())}


class PredictionService:
    async def get_predictions(self, symbol: str) -> Optional[dict]:
        symbol = symbol.upper()
        metadata = load_metadata(symbol)
        if not metadata:
            return None

        cache_key = f"predictions:{symbol}:{metadata['trained_at']}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        result = await asyncio.to_thread(_forecast, symbol, metadata)
        if not result or not result["predictions"]:
            return None

        best_by_horizon = {f"{h}d": d.get("best_model") for h, d in metadata["horizons"].items()}
        overall_best = best_by_horizon.get("1d") or next(iter(result["predictions"]))
        # Forecast path for the chart: best model at each horizon
        path = []
        for h in HORIZONS:
            best = best_by_horizon.get(f"{h}d")
            point = result["predictions"].get(best, {}).get(f"{h}d") if best else None
            if point:
                path.append({"date": point["target_date"], "horizon": f"{h}d", "model": best,
                             "predicted": point["predicted_price"], "lower": point["lower_bound"], "upper": point["upper_bound"]})

        response = {
            "symbol": symbol,
            "available_models": list(result["predictions"].keys()),
            "best_model": overall_best,
            "best_model_by_horizon": best_by_horizon,
            "predictions_by_model": result["predictions"],
            "forecast_path": path,
            "historical_prices": result["historical"],
            "current_price": round(result["last_close"], 2),
            "as_of": result["as_of"],
            "trained_at": metadata["trained_at"],
            "data_source": metadata.get("data_source"),
            "is_demo": metadata.get("is_demo", False),
            "disclaimer": "Model estimates with 95% prediction intervals. Not investment advice.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        await cache_set(cache_key, response, ttl=600)
        return response

    async def get_evaluation_summary(self, symbol: str) -> dict:
        metadata = load_metadata(symbol.upper())
        if not metadata:
            return {"symbol": symbol.upper(), "trained": False, "message": "No trained models found"}

        rows: List[dict] = []
        for h, hdata in metadata["horizons"].items():
            for name, info in hdata["models"].items():
                if "error" in info:
                    rows.append({"model": name, "horizon_days": int(h), "error": info["error"]})
                    continue
                rows.append({
                    "model": name,
                    "display_name": info.get("display_name", name),
                    "horizon_days": int(h),
                    "is_best": hdata.get("best_model") == name,
                    "validation": info["validation"],
                    "test": info["test"],
                    "train_seconds": info.get("train_seconds"),
                    "hyperparameters": info.get("hyperparameters"),
                })
        return {
            "symbol": metadata["symbol"],
            "trained": True,
            "trained_at": metadata["trained_at"],
            "data_source": metadata.get("data_source"),
            "is_demo": metadata.get("is_demo", False),
            "data_range": metadata.get("data_range"),
            "target": metadata.get("target"),
            "feature_columns": metadata.get("feature_columns"),
            "models_skipped": metadata.get("models_skipped", {}),
            "training_seconds": metadata.get("training_seconds"),
            "metrics": rows,
            "naive_baseline": {h: d.get("naive_baseline") for h, d in metadata["horizons"].items()},
            "splits": {h: d.get("split") for h, d in metadata["horizons"].items()},
            "backtest": {h: d["backtest"] for h, d in metadata["horizons"].items() if d.get("backtest")},
            "feature_importance": metadata.get("feature_importance", {}),
        }

    async def list_models(self, symbol: str) -> dict:
        metadata = load_metadata(symbol.upper())
        if not metadata:
            return {"symbol": symbol.upper(), "models": []}
        models = []
        for h, hdata in metadata["horizons"].items():
            for name, info in hdata["models"].items():
                if "error" not in info:
                    models.append({"model": name, "horizon_days": int(h), "artifact": info["artifact"], "trained_at": metadata["trained_at"]})
        return {"symbol": metadata["symbol"], "models": models}

    @staticmethod
    def list_trained_symbols() -> List[dict]:
        from app.config import settings

        out = []
        base = settings.model_storage_path
        if not os.path.isdir(base):
            return out
        for entry in sorted(os.listdir(base)):
            meta = load_metadata(entry.replace("_", "^", 1) if entry.startswith("_") else entry)
            if meta:
                out.append({"symbol": meta["symbol"], "trained_at": meta["trained_at"], "is_demo": meta.get("is_demo", False),
                            "best_model": meta["horizons"].get("1", {}).get("best_model")})
        return out

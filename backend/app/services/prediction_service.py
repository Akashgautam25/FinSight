"""
FinSight AI — Prediction Service
Bridges ML pipeline with FastAPI endpoints.
"""

import os
import glob
from typing import Optional, Dict, List
from datetime import datetime, timedelta, date

import yfinance as yf
import pandas as pd

from app.config import settings
from app.ml.pipeline import TrainingPipeline
from app.ml.feature_engineering import compute_features, FEATURE_COLUMNS
from app.schemas.prediction import TrainRequest


class PredictionService:
    def __init__(self):
        self.storage_base = settings.model_storage_path

    async def train_all_models(self, request: TrainRequest):
        """Called as a background task."""
        try:
            pipeline = TrainingPipeline(
                symbol=request.symbol,
                model_types=request.model_types,
                lookback_years=request.lookback_years,
            )
            results = pipeline.run()
            return results
        except Exception as e:
            return {"error": str(e), "symbol": request.symbol}

    async def get_predictions(self, symbol: str) -> Optional[dict]:
        """Load saved models and generate predictions."""
        from app.ml.models import LinearRegressionModel, RandomForestModel, XGBoostModel
        import joblib

        symbol_dir = os.path.join(self.storage_base, symbol)
        if not os.path.exists(symbol_dir):
            return None

        # Load latest data for prediction
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y", interval="1d")
            if df.empty:
                return None
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            feature_df = compute_features(df)
            X = feature_df[[col for col in FEATURE_COLUMNS if col in feature_df.columns]]
        except Exception:
            return None

        predictions_by_model = {}
        available_models = set()
        best_model = None
        historical = []

        # Build historical prices
        for idx, row in df.tail(90).iterrows():
            historical.append({
                "date": str(idx.date()),
                "close": round(float(row["Close"]), 4),
                "type": "historical",
            })

        HORIZON_MAP = {"linear_regression": LinearRegressionModel, "random_forest": RandomForestModel, "xgboost": XGBoostModel}

        for horizon in [1, 5, 10, 30]:
            horizon_dir = os.path.join(symbol_dir, f"h{horizon}")
            if not os.path.exists(horizon_dir):
                continue

            for model_name, ModelClass in HORIZON_MAP.items():
                pattern = os.path.join(horizon_dir, f"{model_name}_{symbol}_h{horizon}_*.pkl")
                files = sorted(glob.glob(pattern))
                if not files:
                    continue

                latest_file = files[-1]
                try:
                    data = joblib.load(latest_file)
                    model = ModelClass.__new__(ModelClass)
                    model.symbol = symbol
                    model.horizon = horizon
                    model.model = data["model"]
                    model.scaler_X = data["scaler_X"]
                    model.scaler_y = data["scaler_y"]
                    model.feature_columns = data["feature_columns"]

                    feat_cols = [c for c in model.feature_columns if c in X.columns]
                    preds = model.predict(X[feat_cols])

                    # Last prediction = horizon-day forecast
                    last_price = float(df["Close"].iloc[-1])
                    pred_price = float(preds[-1])

                    if model_name not in predictions_by_model:
                        predictions_by_model[model_name] = {}
                    predictions_by_model[model_name][f"{horizon}d"] = {
                        "predicted_price": round(pred_price, 4),
                        "current_price": round(last_price, 4),
                        "predicted_change_pct": round((pred_price - last_price) / last_price * 100, 2),
                        "target_date": str((datetime.now() + timedelta(days=horizon * 1.4)).date()),
                    }
                    available_models.add(model_name)
                except Exception:
                    continue

        if not predictions_by_model:
            return None

        return {
            "symbol": symbol,
            "available_models": list(available_models),
            "best_model": list(available_models)[0],
            "predictions_by_model": predictions_by_model,
            "historical_prices": historical,
            "disclaimer": "Model estimates only. Not investment advice.",
            "fetched_at": datetime.now().isoformat(),
        }

    async def get_evaluation_summary(self, symbol: str) -> dict:
        """Return evaluation metrics for all trained models."""
        import joblib
        symbol_dir = os.path.join(self.storage_base, symbol)
        if not os.path.exists(symbol_dir):
            return {"symbol": symbol, "models": {}, "message": "No trained models found"}

        summary = {"symbol": symbol, "models": {}}

        for horizon in [1, 5, 10, 30]:
            horizon_dir = os.path.join(symbol_dir, f"h{horizon}")
            if not os.path.exists(horizon_dir):
                continue

            for pkl in glob.glob(os.path.join(horizon_dir, "*.pkl")):
                model_name = os.path.basename(pkl).split("_")[0] + "_" + os.path.basename(pkl).split("_")[1]
                # just extract model type prefix
                model_type = "_".join(os.path.basename(pkl).split("_")[:2]) if "random" in pkl else os.path.basename(pkl).split("_")[0]
                key = f"{model_type}_h{horizon}d"
                try:
                    data = joblib.load(pkl)
                    summary["models"][key] = {
                        "model_type": model_type,
                        "horizon_days": horizon,
                        "trained_at": str(data.get("trained_at")),
                        "model_version": data.get("model_version"),
                    }
                except Exception:
                    pass

        return summary

    async def list_models(self, symbol: str) -> dict:
        symbol_dir = os.path.join(self.storage_base, symbol)
        if not os.path.exists(symbol_dir):
            return {"symbol": symbol, "models": []}

        models = []
        for f in glob.glob(os.path.join(symbol_dir, "**", "*.pkl"), recursive=True):
            models.append({"path": f, "name": os.path.basename(f)})
        for f in glob.glob(os.path.join(symbol_dir, "**", "*.pt"), recursive=True):
            models.append({"path": f, "name": os.path.basename(f)})

        return {"symbol": symbol, "models": models}

"""
FinSight AI — ML Training Pipeline
Orchestrates data loading, feature engineering, training, and evaluation.
"""

import os
from typing import List, Optional, Dict
from datetime import datetime

import yfinance as yf
import pandas as pd

from app.config import settings
from app.ml.feature_engineering import compute_features, create_target, time_series_split, FEATURE_COLUMNS
from app.ml.evaluation import evaluate_model, select_best_model
from app.ml.models import LinearRegressionModel, RandomForestModel, XGBoostModel, LSTMModel

HORIZONS = [1, 5, 10, 30]  # trading days

MODEL_REGISTRY = {
    "linear_regression": LinearRegressionModel,
    "random_forest": RandomForestModel,
    "xgboost": XGBoostModel,
    "lstm": LSTMModel,
}


class TrainingPipeline:
    """
    End-to-end ML training pipeline.
    Prevents data leakage via strict chronological splits.
    """

    def __init__(self, symbol: str, model_types: Optional[List[str]] = None, lookback_years: int = 5):
        self.symbol = symbol
        self.model_types = model_types or list(MODEL_REGISTRY.keys())
        self.lookback_years = lookback_years
        self.storage_dir = os.path.join(settings.model_storage_path, symbol)

    def load_data(self) -> pd.DataFrame:
        """Download OHLCV data from yfinance."""
        ticker = yf.Ticker(self.symbol)
        period = f"{self.lookback_years}y"
        df = ticker.history(period=period, interval="1d")

        if df.empty:
            raise ValueError(f"No data returned for {self.symbol}")

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df

    def run(self) -> Dict:
        """
        Full pipeline: data → features → split → train all models → evaluate → save.
        Returns evaluation summary for all models and all horizons.
        """
        raw_df = self.load_data()
        feature_df = compute_features(raw_df)

        results = {}

        for horizon in HORIZONS:
            X_all, y_all = create_target(feature_df, horizon=horizon)
            X_feat = X_all[[col for col in FEATURE_COLUMNS if col in X_all.columns]]

            X_train, X_val, X_test, y_train, y_val, y_test = time_series_split(X_feat, y_all)

            if len(X_train) < 100:
                continue  # Insufficient data for this horizon

            horizon_results = {}

            for model_name in self.model_types:
                if model_name not in MODEL_REGISTRY:
                    continue

                try:
                    ModelClass = MODEL_REGISTRY[model_name]
                    model_instance = ModelClass(symbol=self.symbol, horizon=horizon)

                    # Train
                    model_instance.fit(X_train, y_train, X_val, y_val)

                    # Evaluate on validation and test sets
                    val_preds = model_instance.predict(X_val)
                    test_preds = model_instance.predict(X_test)

                    val_metrics = evaluate_model(y_val.values, val_preds, "validation")
                    test_metrics = evaluate_model(y_test.values, test_preds, "test")

                    # Save model
                    model_path = model_instance.save(
                        os.path.join(self.storage_dir, f"h{horizon}")
                    )

                    horizon_results[model_name] = {
                        "model_path": model_path,
                        "validation": val_metrics,
                        "test": test_metrics,
                        "trained_at": model_instance.trained_at.isoformat(),
                        "training_period_start": str(X_train.index[0].date()),
                        "training_period_end": str(X_train.index[-1].date()),
                        "feature_columns": model_instance.feature_columns,
                    }

                except Exception as e:
                    horizon_results[model_name] = {"error": str(e)}

            best = select_best_model({
                k: v.get("validation", {}) for k, v in horizon_results.items()
                if "error" not in v
            })
            results[f"horizon_{horizon}d"] = {
                "models": horizon_results,
                "best_model": best,
            }

        return {
            "symbol": self.symbol,
            "trained_at": datetime.now().isoformat(),
            "horizons": results,
        }

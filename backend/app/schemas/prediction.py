"""
FinSight AI — Prediction Pydantic Schemas
"""

from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel


class TrainRequest(BaseModel):
    symbol: str
    model_types: List[str] = ["linear_regression", "random_forest", "xgboost", "lstm"]
    lookback_years: int = 5


class PredictionPoint(BaseModel):
    target_date: date
    predicted_price: float
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    confidence_score: Optional[float]


class ModelEvaluationResponse(BaseModel):
    model_type: str
    model_version: str
    mae: Optional[float]
    mse: Optional[float]
    rmse: Optional[float]
    mape: Optional[float]
    r_squared: Optional[float]
    directional_accuracy: Optional[float]
    trained_at: datetime
    training_period_start: Optional[str]
    training_period_end: Optional[str]


class PredictionResponse(BaseModel):
    symbol: str
    model_type: str
    prediction_date: date
    predictions: List[PredictionPoint]
    evaluation: Optional[ModelEvaluationResponse]
    disclaimer: str = (
        "These are model-generated estimates, not guaranteed forecasts. "
        "Past performance does not guarantee future results."
    )
    is_demo: bool = False


class AllModelPredictionsResponse(BaseModel):
    symbol: str
    available_models: List[str]
    best_model: str
    predictions_by_model: dict
    historical_prices: List[dict]

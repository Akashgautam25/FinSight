"""
FinSight AI — Prediction Pydantic Schemas
"""

from typing import List

from pydantic import BaseModel, Field, field_validator

ALL_MODELS = ["linear_regression", "random_forest", "xgboost", "lstm"]


class TrainRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    model_types: List[str] = Field(default_factory=lambda: list(ALL_MODELS))
    lookback_years: int = Field(5, ge=2, le=10)

    @field_validator("symbol")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("model_types")
    @classmethod
    def known_models(cls, v: List[str]) -> List[str]:
        unknown = [m for m in v if m not in ALL_MODELS]
        if unknown:
            raise ValueError(f"Unknown model types: {unknown}. Choose from {ALL_MODELS}")
        return v or list(ALL_MODELS)

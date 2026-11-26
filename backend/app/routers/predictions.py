"""
FinSight AI — ML Predictions Router
"""

from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser
from app.ml.jobs import training_jobs
from app.ml.models import model_availability
from app.ml.pipeline import load_metadata
from app.schemas.prediction import TrainRequest
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.post("/train", status_code=202)
async def trigger_training(payload: TrainRequest, current_user: CurrentUser):
    """Queue background training for a symbol (poll /predictions/{symbol}/status)."""
    job = training_jobs.submit(payload.symbol, payload.model_types, payload.lookback_years, user_id=current_user.id)
    return {"message": f"Training queued for {job['symbol']}", "job": job}


@router.get("/trained")
async def list_trained(_: CurrentUser):
    return {"symbols": PredictionService.list_trained_symbols(), "model_availability": model_availability()}


@router.get("/{symbol}/status")
async def training_status(symbol: str, _: CurrentUser):
    job = training_jobs.status(symbol)
    if job:
        return job
    meta = load_metadata(symbol.upper())
    if meta:
        return {"symbol": symbol.upper(), "status": "completed", "progress": 1.0, "message": "Models available",
                "finished_at": meta["trained_at"]}
    return {"symbol": symbol.upper(), "status": "not_trained", "progress": 0.0, "message": "No models trained yet"}


@router.get("/{symbol}")
async def get_predictions(symbol: str, _: CurrentUser):
    result = await PredictionService().get_predictions(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"No trained models found for {symbol.upper()}. Train them first.")
    return result


@router.get("/{symbol}/evaluation")
async def get_model_evaluation(symbol: str, _: CurrentUser):
    return await PredictionService().get_evaluation_summary(symbol.upper())


@router.get("/{symbol}/models")
async def list_models(symbol: str, _: CurrentUser):
    return await PredictionService().list_models(symbol.upper())

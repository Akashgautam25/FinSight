"""
FinSight AI — ML Predictions Router
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from app.dependencies import CurrentUser
from app.schemas.prediction import TrainRequest, PredictionResponse, AllModelPredictionsResponse
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.post("/train")
async def trigger_training(
    payload: TrainRequest,
    background_tasks: BackgroundTasks,
    _: CurrentUser = Depends(),
):
    """Trigger async model training for a symbol."""
    service = PredictionService()
    background_tasks.add_task(service.train_all_models, payload)
    return {
        "message": f"Training initiated for {payload.symbol}",
        "models": payload.model_types,
        "status": "queued",
    }


@router.get("/{symbol}", response_model=AllModelPredictionsResponse)
async def get_predictions(symbol: str, _: CurrentUser = Depends()):
    service = PredictionService()
    result = await service.get_predictions(symbol.upper())
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No trained models found for {symbol}. Trigger /predictions/train first.",
        )
    return result


@router.get("/{symbol}/evaluation")
async def get_model_evaluation(symbol: str, _: CurrentUser = Depends()):
    service = PredictionService()
    return await service.get_evaluation_summary(symbol.upper())


@router.get("/{symbol}/models")
async def list_models(symbol: str, _: CurrentUser = Depends()):
    service = PredictionService()
    return await service.list_models(symbol.upper())

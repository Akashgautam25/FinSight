"""
FinSight AI — Portfolio Optimization Router
"""

from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser
from app.schemas.ai import OptimizationRequest, OptimizationResponse
from app.services.optimization_service import OptimizationError, OptimizationService

router = APIRouter()


@router.post("/efficient-frontier")
async def efficient_frontier(payload: OptimizationRequest, _: CurrentUser):
    try:
        return await OptimizationService().compute_efficient_frontier(payload)
    except OptimizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/max-sharpe", response_model=OptimizationResponse)
async def max_sharpe(payload: OptimizationRequest, _: CurrentUser):
    try:
        return await OptimizationService().optimize(payload, method="max_sharpe")
    except OptimizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/min-volatility", response_model=OptimizationResponse)
async def min_volatility(payload: OptimizationRequest, _: CurrentUser):
    try:
        return await OptimizationService().optimize(payload, method="min_volatility")
    except OptimizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

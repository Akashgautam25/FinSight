"""
FinSight AI — Portfolio Optimization Router
"""

from fastapi import APIRouter, Depends
from app.dependencies import CurrentUser
from app.schemas.ai import OptimizationRequest, OptimizationResponse
from app.services.optimization_service import OptimizationService

router = APIRouter()


@router.post("/efficient-frontier")
async def efficient_frontier(payload: OptimizationRequest, _: CurrentUser = Depends()):
    service = OptimizationService()
    return await service.compute_efficient_frontier(payload)


@router.post("/max-sharpe", response_model=OptimizationResponse)
async def max_sharpe(payload: OptimizationRequest, _: CurrentUser = Depends()):
    service = OptimizationService()
    return await service.optimize(payload, method="max_sharpe")


@router.post("/min-volatility", response_model=OptimizationResponse)
async def min_volatility(payload: OptimizationRequest, _: CurrentUser = Depends()):
    service = OptimizationService()
    return await service.optimize(payload, method="min_volatility")

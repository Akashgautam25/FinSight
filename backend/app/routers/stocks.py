"""
FinSight AI — Stocks Router
"""

from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.stock import (
    StockDetailResponse, StockSearchResult, MarketOverviewResponse,
    StockCompareRequest, TechnicalIndicatorsResponse,
)
from app.services.stock_service import StockService

router = APIRouter()


@router.get("/search", response_model=List[StockSearchResult])
async def search_stocks(
    q: str = Query(..., min_length=1, description="Company name or ticker symbol"),
    limit: int = Query(10, le=50),
    _: CurrentUser = Depends(),
):
    service = StockService()
    return await service.search(q, limit)


@router.get("/market/overview", response_model=MarketOverviewResponse)
async def market_overview(_: CurrentUser = Depends()):
    service = StockService()
    return await service.get_market_overview()


@router.get("/compare")
async def compare_stocks(
    symbols: str = Query(..., description="Comma-separated symbols, max 5"),
    period: str = Query("1y"),
    _: CurrentUser = Depends(),
):
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:5]
    service = StockService()
    return await service.compare_stocks(symbol_list, period)


@router.get("/{symbol}", response_model=StockDetailResponse)
async def get_stock(symbol: str, _: CurrentUser = Depends()):
    service = StockService()
    result = await service.get_stock_detail(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    return result


@router.get("/{symbol}/history")
async def get_stock_history(
    symbol: str,
    period: str = Query("1y", description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max"),
    interval: str = Query("1d", description="1m, 5m, 15m, 1h, 1d, 1wk, 1mo"),
    _: CurrentUser = Depends(),
):
    service = StockService()
    return await service.get_history(symbol.upper(), period, interval)


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str, _: CurrentUser = Depends()):
    service = StockService()
    return await service.get_fundamentals(symbol.upper())


@router.get("/{symbol}/technical", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(symbol: str, _: CurrentUser = Depends()):
    service = StockService()
    return await service.get_technical_indicators(symbol.upper())

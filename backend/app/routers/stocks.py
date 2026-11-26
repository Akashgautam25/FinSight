"""
FinSight AI — Stocks Router
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import CurrentUser
from app.schemas.stock import MarketOverviewResponse, StockDetailResponse, StockSearchResult, TechnicalIndicatorsResponse
from app.services.stock_service import StockService

router = APIRouter()


@router.get("/search", response_model=List[StockSearchResult])
async def search_stocks(
    _: CurrentUser,
    q: str = Query(..., min_length=1, max_length=50, description="Company name or ticker symbol"),
    limit: int = Query(10, ge=1, le=25),
):
    return await StockService().search(q, limit)


@router.get("/market/overview", response_model=MarketOverviewResponse)
async def market_overview(_: CurrentUser):
    return await StockService().get_market_overview()


@router.get("/quotes")
async def batch_quotes(_: CurrentUser, symbols: str = Query(..., description="Comma-separated symbols, max 25")):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:25]
    return await StockService().get_quotes(symbol_list)


@router.get("/compare")
async def compare_stocks(
    _: CurrentUser,
    symbols: str = Query(..., description="Comma-separated symbols, 2–5"),
    period: str = Query("1y"),
):
    symbol_list = list(dict.fromkeys(s.strip().upper() for s in symbols.split(",") if s.strip()))[:5]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="Provide at least one symbol")
    return await StockService().compare_stocks(symbol_list, period)


@router.get("/{symbol}", response_model=StockDetailResponse)
async def get_stock(symbol: str, _: CurrentUser):
    result = await StockService().get_stock_detail(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol.upper()}' not found")
    return result


@router.get("/{symbol}/history")
async def get_stock_history(
    symbol: str,
    _: CurrentUser,
    period: str = Query("1y", description="1d, 5d, 1mo, 3mo, 6mo, ytd, 1y, 2y, 5y, max"),
    interval: str = Query("1d", description="5m, 15m, 1h, 1d, 1wk, 1mo"),
    indicators: bool = Query(False, description="Include SMA/Bollinger/RSI/MACD overlays"),
):
    return await StockService().get_history(symbol.upper(), period, interval, indicators)


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str, _: CurrentUser):
    return await StockService().get_fundamentals(symbol.upper())


@router.get("/{symbol}/technical", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(symbol: str, _: CurrentUser):
    try:
        return await StockService().get_technical_indicators(symbol.upper())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

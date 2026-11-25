"""
FinSight AI — News Router
"""

from typing import Optional
from fastapi import APIRouter, Query, Depends
from app.dependencies import CurrentUser
from app.services.news_service import NewsService

router = APIRouter()


@router.get("")
async def get_market_news(
    limit: int = Query(20, le=100),
    category: Optional[str] = None,
    _: CurrentUser = Depends(),
):
    service = NewsService()
    return await service.get_market_news(limit=limit, category=category)


@router.get("/{symbol}")
async def get_stock_news(
    symbol: str,
    limit: int = Query(20, le=100),
    days: int = Query(7, le=30),
    _: CurrentUser = Depends(),
):
    service = NewsService()
    return await service.get_stock_news(symbol.upper(), limit=limit, days=days)


@router.get("/{symbol}/sentiment")
async def get_sentiment(
    symbol: str,
    days: int = Query(30, le=90),
    _: CurrentUser = Depends(),
):
    service = NewsService()
    return await service.get_sentiment_summary(symbol.upper(), days=days)


@router.get("/sectors/{sector}")
async def get_sector_news(
    sector: str,
    limit: int = Query(20, le=50),
    _: CurrentUser = Depends(),
):
    service = NewsService()
    return await service.get_sector_news(sector, limit=limit)

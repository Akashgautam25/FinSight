"""
FinSight AI — News & Sentiment Router
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser
from app.services.news_service import NewsService
from app.services.sentiment_service import SentimentService, model_status

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


@router.get("")
async def get_market_news(
    _: CurrentUser,
    limit: int = Query(20, ge=1, le=60),
    category: Optional[str] = Query(None, description="all, technology, finance, healthcare, energy, consumer, india"),
):
    return await NewsService().get_market_news(limit=limit, category=category)


@router.get("/sentiment/model")
async def sentiment_model(_: CurrentUser):
    return model_status()


@router.post("/sentiment/analyze")
async def analyze_text(payload: AnalyzeRequest, _: CurrentUser):
    """Score any piece of financial text (handy for demos and testing)."""
    result = await SentimentService().analyze(payload.text)
    return {"text": payload.text, **result}


@router.get("/sectors/{sector}")
async def get_sector_news(sector: str, _: CurrentUser, limit: int = Query(20, ge=1, le=60)):
    return await NewsService().get_sector_news(sector, limit=limit)


@router.get("/{symbol}")
async def get_stock_news(symbol: str, _: CurrentUser, limit: int = Query(20, ge=1, le=50), days: int = Query(7, ge=1, le=60)):
    return await NewsService().get_stock_news(symbol.upper(), limit=limit, days=days)


@router.get("/{symbol}/sentiment")
async def get_sentiment(symbol: str, _: CurrentUser, days: int = Query(30, ge=1, le=90)):
    return await NewsService().get_sentiment_summary(symbol.upper(), days=days)

"""
FinSight AI — News & AI Pydantic Schemas
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class NewsItemResponse(BaseModel):
    id: str
    symbol: Optional[str]
    title: str
    summary: Optional[str]
    url: str
    source: Optional[str]
    author: Optional[str]
    published_at: Optional[datetime]
    category: Optional[str]
    sentiment: Optional[str]
    positive_score: Optional[float]
    negative_score: Optional[float]
    neutral_score: Optional[float]
    compound_score: Optional[float]

    model_config = {"from_attributes": True}


class SentimentSummaryResponse(BaseModel):
    symbol: str
    overall_sentiment: str
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    avg_compound_score: float
    news_count: int
    period_days: int
    as_of: datetime


# AI Assistant Schemas
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class SourceCitation(BaseModel):
    type: str  # market_data / news / calculation / document
    title: str
    url: Optional[str]
    timestamp: Optional[datetime]
    is_verified: bool = True


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    sources: List[SourceCitation] = []
    tool_calls_made: List[str] = []
    is_ai_generated: bool = True
    disclaimer: str = "AI-generated interpretation. Verify all data before making financial decisions."


class GenerateReportRequest(BaseModel):
    symbol: str
    include_predictions: bool = True
    include_sentiment: bool = True
    report_title: Optional[str] = None


class OptimizationRequest(BaseModel):
    symbols: List[str]
    period: str = "2y"
    risk_free_rate: float = 0.05
    min_weight: float = 0.0
    max_weight: float = 1.0
    long_only: bool = True


class OptimizationResponse(BaseModel):
    method: str
    weights: dict
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    efficient_frontier: Optional[List[dict]]
    disclaimer: str = (
        "Portfolio optimization uses historical data and mathematical models. "
        "Optimized allocations are not guaranteed to perform optimally in future markets."
    )

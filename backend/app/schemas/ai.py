"""
FinSight AI — AI Assistant, Report and Optimization Pydantic Schemas
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── AI Assistant ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None


class SourceCitation(BaseModel):
    type: str  # market_data / technicals / news / prediction / portfolio / knowledge_base
    title: str
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    is_verified: bool = True


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    sources: List[SourceCitation] = []
    tool_calls_made: List[str] = []
    llm_provider: str = "offline"
    suggestions: List[str] = []
    is_ai_generated: bool = True
    disclaimer: str = "AI-generated interpretation. Verify all data before making financial decisions."


class GenerateReportRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    include_predictions: bool = True
    include_sentiment: bool = True
    report_title: Optional[str] = None


# ── Optimization ─────────────────────────────────────────────────────────────

class OptimizationRequest(BaseModel):
    symbols: List[str] = Field(..., min_length=2, max_length=15)
    period: str = "2y"
    risk_free_rate: float = Field(0.05, ge=0, le=0.25)
    min_weight: float = Field(0.0, ge=0, le=1)
    max_weight: float = Field(1.0, gt=0, le=1)
    long_only: bool = True
    investment_amount: Optional[float] = Field(None, gt=0)


class OptimizationResponse(BaseModel):
    method: str
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    efficient_frontier: Optional[List[dict]] = None
    allocation: Optional[dict] = None
    excluded_symbols: List[str] = []
    is_demo: bool = False
    disclaimer: str = (
        "Portfolio optimization uses historical data and mathematical models. "
        "Optimized allocations are not guaranteed to perform optimally in future markets."
    )

"""
FinSight AI — Portfolio Pydantic Schemas
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class CreatePortfolioRequest(BaseModel):
    name: str
    description: Optional[str] = None
    currency: str = "USD"


class AddTransactionRequest(BaseModel):
    symbol: str
    transaction_type: str  # BUY or SELL
    quantity: float
    price: float
    fees: float = 0.0
    transaction_date: datetime
    notes: Optional[str] = None


class HoldingResponse(BaseModel):
    id: str
    symbol: str
    quantity: float
    avg_purchase_price: float
    current_price: Optional[float]
    current_value: Optional[float]
    unrealized_pnl: Optional[float]
    unrealized_pnl_pct: Optional[float]
    weight: Optional[float]  # % of portfolio

    model_config = {"from_attributes": True}


class PortfolioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    currency: str
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioAnalyticsResponse(BaseModel):
    portfolio_id: str
    total_invested: float
    current_value: float
    absolute_return: float
    return_pct: float
    daily_return: Optional[float]
    annualized_return: Optional[float]
    portfolio_volatility: Optional[float]
    max_drawdown: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    beta: Optional[float]
    holdings: List[HoldingResponse]
    sector_allocation: Optional[dict]
    asset_allocation: Optional[dict]
    calculated_at: datetime

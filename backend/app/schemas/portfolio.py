"""
FinSight AI — Portfolio Pydantic Schemas
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CreatePortfolioRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    currency: str = "USD"


class UpdatePortfolioRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class AddTransactionRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    transaction_type: Literal["BUY", "SELL", "buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    fees: float = Field(0.0, ge=0)
    transaction_date: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def upper_symbol(cls, v: str) -> str:
        return v.strip().upper()


class TransactionResponse(BaseModel):
    id: str
    symbol: str
    transaction_type: str
    quantity: float
    price: float
    fees: float
    transaction_date: datetime
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class HoldingResponse(BaseModel):
    id: str
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    quantity: float
    avg_purchase_price: float
    cost_basis: float
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    day_change_pct: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    weight: Optional[float] = None  # % of portfolio market value
    is_demo: bool = False

    model_config = {"from_attributes": True}


class PortfolioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
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
    realized_pnl: float = 0.0
    daily_return: Optional[float] = None          # %
    annualized_return: Optional[float] = None     # %
    portfolio_volatility: Optional[float] = None  # % annualized
    max_drawdown: Optional[float] = None          # %
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    beta: Optional[float] = None                  # vs S&P 500
    var_95: Optional[float] = None                # 1-day historical VaR, currency
    cvar_95: Optional[float] = None               # 1-day expected shortfall, currency
    benchmark_return: Optional[float] = None      # S&P 500 over the same window, %
    holdings: List[HoldingResponse]
    sector_allocation: Optional[dict] = None
    asset_allocation: Optional[dict] = None
    performance: List[dict] = []                  # [{date, portfolio, benchmark}] indexed to 100
    methodology: Optional[str] = None
    is_demo: bool = False
    calculated_at: datetime

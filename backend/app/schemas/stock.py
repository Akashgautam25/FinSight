"""
FinSight AI — Stock Pydantic Schemas
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    currency: str = "USD"

    model_config = {"from_attributes": True}


class FinancialMetricsResponse(BaseModel):
    symbol: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    profit_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    free_cash_flow: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    extra_metrics: Optional[dict] = None
    as_of_date: Optional[date] = None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class StockDetailResponse(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    currency: str = "USD"
    description: Optional[str] = None
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    metrics: Optional[FinancialMetricsResponse] = None
    last_updated: Optional[datetime] = None
    data_source: str = "yahoo_finance"
    is_delayed: bool = True
    is_demo: bool = False


class IndicatorSignal(BaseModel):
    indicator: str
    signal: str  # bullish / bearish / neutral
    detail: str


class TechnicalIndicatorsResponse(BaseModel):
    symbol: str
    date: date
    close: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    volatility_30d: Optional[float] = None  # annualized, %
    signals: List[IndicatorSignal] = []
    overall_signal: str = "neutral"
    is_demo: bool = False


class MarketOverviewResponse(BaseModel):
    indices: List[dict]
    top_gainers: List[dict]
    top_losers: List[dict]
    most_active: List[dict]
    market_status: str
    as_of: datetime
    is_demo: bool = False

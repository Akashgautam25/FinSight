"""
FinSight AI — Stock Pydantic Schemas
"""

from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    country: Optional[str]
    currency: str

    model_config = {"from_attributes": True}


class StockPricePoint(BaseModel):
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: float
    adj_close: Optional[float]
    volume: Optional[int]


class FinancialMetricsResponse(BaseModel):
    symbol: str
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    eps: Optional[float]
    dividend_yield: Optional[float]
    beta: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    debt_to_equity: Optional[float]
    profit_margin: Optional[float]
    revenue_growth: Optional[float]
    free_cash_flow: Optional[float]
    week_52_high: Optional[float]
    week_52_low: Optional[float]
    extra_metrics: Optional[dict]
    as_of_date: Optional[date]
    fetched_at: datetime

    model_config = {"from_attributes": True}


class StockDetailResponse(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    country: Optional[str]
    currency: str
    current_price: Optional[float]
    previous_close: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]
    volume: Optional[int]
    metrics: Optional[FinancialMetricsResponse]
    last_updated: Optional[datetime]
    data_source: str = "yfinance"
    is_delayed: bool = True


class TechnicalIndicatorsResponse(BaseModel):
    symbol: str
    date: date
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    ema_12: Optional[float]
    ema_26: Optional[float]
    rsi_14: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    macd_hist: Optional[float]
    bb_upper: Optional[float]
    bb_middle: Optional[float]
    bb_lower: Optional[float]
    atr_14: Optional[float]


class MarketOverviewResponse(BaseModel):
    indices: List[dict]
    top_gainers: List[dict]
    top_losers: List[dict]
    most_active: List[dict]
    market_status: str
    as_of: datetime


class StockCompareRequest(BaseModel):
    symbols: List[str]
    period: str = "1y"

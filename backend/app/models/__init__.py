"""
FinSight AI — SQLAlchemy ORM Models
All 20 tables as specified in the database schema.
"""

import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Boolean, Text, Numeric, BigInteger, Integer,
    ForeignKey, DateTime, Date, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, JSONType


def gen_uuid():
    return str(uuid.uuid4())


# ── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String(50), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped[Optional["UserProfile"]] = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    preferences: Mapped[Optional["UserPreferences"]] = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    portfolios: Mapped[list["Portfolio"]] = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    watchlists: Mapped[list["Watchlist"]] = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSession"]] = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    price_alerts: Mapped[list["PriceAlert"]] = relationship("PriceAlert", back_populates="user", cascade="all, delete-orphan")
    research_reports: Mapped[list["ResearchReport"]] = relationship("ResearchReport", back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    default_currency: Mapped[str] = mapped_column(String(10), default="USD")
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    notification_prefs: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="profile")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    theme: Mapped[str] = mapped_column(String(20), default="dark")
    default_market: Mapped[str] = mapped_column(String(20), default="US")
    dashboard_layout: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    alert_channels: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)

    user: Mapped["User"] = relationship("User", back_populates="preferences")


# ── Portfolio ─────────────────────────────────────────────────────────────────

class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="portfolios")
    holdings: Mapped[list["PortfolioHolding"]] = relationship("PortfolioHolding", back_populates="portfolio", cascade="all, delete-orphan")
    transactions: Mapped[list["PortfolioTransaction"]] = relationship("PortfolioTransaction", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "symbol", name="uq_portfolio_symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    portfolio_id: Mapped[str] = mapped_column(String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False), nullable=False)
    avg_purchase_price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    portfolio_id: Mapped[str] = mapped_column(String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY / SELL
    quantity: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False)
    fees: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), default=0)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="transactions")


# ── Watchlist ─────────────────────────────────────────────────────────────────

class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="watchlists")
    stocks: Mapped[list["WatchlistStock"]] = relationship("WatchlistStock", back_populates="watchlist", cascade="all, delete-orphan", order_by="WatchlistStock.sort_order")


class WatchlistStock(Base):
    __tablename__ = "watchlist_stocks"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    watchlist_id: Mapped[str] = mapped_column(String(36), ForeignKey("watchlists.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watchlist: Mapped["Watchlist"] = relationship("Watchlist", back_populates="stocks")


# ── Stocks ────────────────────────────────────────────────────────────────────

class Stock(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(50))
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    prices: Mapped[list["StockPrice"]] = relationship("StockPrice", back_populates="stock")
    metrics: Mapped[Optional["FinancialMetrics"]] = relationship("FinancialMetrics", back_populates="stock", uselist=False)


class StockPrice(Base):
    __tablename__ = "stock_prices"
    __table_args__ = (
        UniqueConstraint("symbol", "price_date", name="uq_stock_date"),
        Index("ix_stock_prices_symbol_date", "symbol", "price_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol", ondelete="CASCADE"), index=True)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    high: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    low: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    close: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False)
    adj_close: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    data_source: Mapped[str] = mapped_column(String(50), default="yfinance")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock: Mapped["Stock"] = relationship("Stock", back_populates="prices")


class FinancialMetrics(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol", ondelete="CASCADE"), unique=True, index=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Numeric(24, 2, asdecimal=False))
    pe_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False))
    eps: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False))
    dividend_yield: Mapped[Optional[float]] = mapped_column(Numeric(8, 6, asdecimal=False))
    beta: Mapped[Optional[float]] = mapped_column(Numeric(8, 4, asdecimal=False))
    roe: Mapped[Optional[float]] = mapped_column(Numeric(8, 4, asdecimal=False))
    roa: Mapped[Optional[float]] = mapped_column(Numeric(8, 4, asdecimal=False))
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False))
    profit_margin: Mapped[Optional[float]] = mapped_column(Numeric(8, 4, asdecimal=False))
    revenue_growth: Mapped[Optional[float]] = mapped_column(Numeric(8, 4, asdecimal=False))
    free_cash_flow: Mapped[Optional[float]] = mapped_column(Numeric(24, 2, asdecimal=False))
    week_52_high: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    week_52_low: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    extra_metrics: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    as_of_date: Mapped[Optional[date]] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock: Mapped["Stock"] = relationship("Stock", back_populates="metrics")


# ── News & Sentiment ──────────────────────────────────────────────────────────

class StockNews(Base):
    __tablename__ = "stock_news"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255))
    author: Mapped[Optional[str]] = mapped_column(String(255))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sentiment: Mapped[Optional["SentimentAnalysis"]] = relationship("SentimentAnalysis", back_populates="news", uselist=False)


class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    news_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_news.id", ondelete="CASCADE"), unique=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    sentiment: Mapped[str] = mapped_column(String(10), nullable=False)  # positive/negative/neutral
    positive_score: Mapped[float] = mapped_column(Numeric(6, 4, asdecimal=False), default=0)
    negative_score: Mapped[float] = mapped_column(Numeric(6, 4, asdecimal=False), default=0)
    neutral_score: Mapped[float] = mapped_column(Numeric(6, 4, asdecimal=False), default=0)
    compound_score: Mapped[float] = mapped_column(Numeric(6, 4, asdecimal=False), default=0)
    model_used: Mapped[str] = mapped_column(String(100), default="finbert")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    news: Mapped["StockNews"] = relationship("StockNews", back_populates="sentiment")


# ── ML Models & Predictions ───────────────────────────────────────────────────

class MLModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)  # linear_regression, random_forest, xgboost, lstm
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_path: Mapped[str] = mapped_column(String(500), nullable=False)
    hyperparameters: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    feature_columns: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    training_period_start: Mapped[Optional[str]] = mapped_column(String(20))
    training_period_end: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluations: Mapped[list["ModelEvaluation"]] = relationship("ModelEvaluation", back_populates="model", cascade="all, delete-orphan")
    predictions: Mapped[list["ModelPrediction"]] = relationship("ModelPrediction", back_populates="model", cascade="all, delete-orphan")


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ml_models.id", ondelete="CASCADE"), index=True)
    mae: Mapped[Optional[float]] = mapped_column(Numeric(24, 6, asdecimal=False))
    mse: Mapped[Optional[float]] = mapped_column(Numeric(24, 6, asdecimal=False))
    rmse: Mapped[Optional[float]] = mapped_column(Numeric(24, 6, asdecimal=False))
    mape: Mapped[Optional[float]] = mapped_column(Numeric(8, 4, asdecimal=False))
    r_squared: Mapped[Optional[float]] = mapped_column(Numeric(8, 6, asdecimal=False))
    directional_accuracy: Mapped[Optional[float]] = mapped_column(Numeric(6, 4, asdecimal=False))
    evaluation_split: Mapped[str] = mapped_column(String(20), default="test")
    evaluation_details: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    model: Mapped["MLModel"] = relationship("MLModel", back_populates="evaluations")


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ml_models.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False)
    lower_bound: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    upper_bound: Mapped[Optional[float]] = mapped_column(Numeric(18, 4, asdecimal=False))
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4, asdecimal=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    model: Mapped["MLModel"] = relationship("MLModel", back_populates="predictions")


# ── Reports, Chat, Alerts, Notifications ─────────────────────────────────────

class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="generating")  # generating / ready / failed
    report_data: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    share_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="research_reports")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="New Conversation")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant / system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[dict]] = mapped_column(JSONType, default=list)
    tool_calls: Mapped[Optional[dict]] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)  # price_above, price_below, pct_change
    target_value: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)  # above / below
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="price_alerts")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONType, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="notifications")

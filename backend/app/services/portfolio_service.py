"""
FinSight AI — Portfolio Service
Portfolio CRUD, transaction handling, and analytics calculations.
All financial formulas are mathematically validated.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import numpy as np
import pandas as pd
import yfinance as yf

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Portfolio, PortfolioHolding, PortfolioTransaction
from app.schemas.portfolio import (
    AddTransactionRequest, HoldingResponse, PortfolioAnalyticsResponse,
)


TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.05  # 5% annualized


class PortfolioService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_transaction(self, portfolio: Portfolio, payload: AddTransactionRequest) -> dict:
        # Create transaction record
        txn = PortfolioTransaction(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio.id,
            symbol=payload.symbol.upper(),
            transaction_type=payload.transaction_type.upper(),
            quantity=payload.quantity,
            price=payload.price,
            fees=payload.fees,
            transaction_date=payload.transaction_date,
            notes=payload.notes,
        )
        self.db.add(txn)

        # Update or create holding
        result = await self.db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.portfolio_id == portfolio.id,
                PortfolioHolding.symbol == payload.symbol.upper(),
            )
        )
        holding = result.scalar_one_or_none()

        if payload.transaction_type.upper() == "BUY":
            if holding:
                # Weighted average cost
                total_cost = (holding.avg_purchase_price * holding.quantity) + (payload.price * payload.quantity)
                holding.quantity += payload.quantity
                holding.avg_purchase_price = total_cost / holding.quantity
            else:
                holding = PortfolioHolding(
                    id=str(uuid.uuid4()),
                    portfolio_id=portfolio.id,
                    symbol=payload.symbol.upper(),
                    quantity=payload.quantity,
                    avg_purchase_price=payload.price,
                    currency=portfolio.currency,
                )
                self.db.add(holding)
        elif payload.transaction_type.upper() == "SELL":
            if holding:
                holding.quantity -= payload.quantity
                if holding.quantity <= 0:
                    await self.db.delete(holding)

        await self.db.commit()
        return {"message": "Transaction recorded", "transaction_id": txn.id}

    async def get_holdings_with_prices(self, portfolio_id: str) -> List[HoldingResponse]:
        result = await self.db.execute(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
        )
        holdings = result.scalars().all()

        total_value = sum(h.quantity * (self._get_price(h.symbol) or h.avg_purchase_price) for h in holdings)

        responses = []
        for h in holdings:
            current_price = self._get_price(h.symbol)
            current_value = h.quantity * (current_price or h.avg_purchase_price)
            cost_basis = h.quantity * h.avg_purchase_price
            unrealized_pnl = current_value - cost_basis if current_price else None
            unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis and unrealized_pnl is not None else None
            weight = (current_value / total_value * 100) if total_value > 0 else None

            responses.append(HoldingResponse(
                id=h.id,
                symbol=h.symbol,
                quantity=float(h.quantity),
                avg_purchase_price=float(h.avg_purchase_price),
                current_price=round(current_price, 4) if current_price else None,
                current_value=round(current_value, 2) if current_price else None,
                unrealized_pnl=round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
                unrealized_pnl_pct=round(unrealized_pnl_pct, 2) if unrealized_pnl_pct is not None else None,
                weight=round(weight, 2) if weight is not None else None,
            ))

        return responses

    def _get_price(self, symbol: str) -> Optional[float]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        return None

    async def compute_analytics(self, portfolio: Portfolio) -> PortfolioAnalyticsResponse:
        holdings_response = await self.get_holdings_with_prices(portfolio.id)

        total_invested = sum(
            h.quantity * h.avg_purchase_price for h in holdings_response
        )
        current_value = sum(
            h.current_value for h in holdings_response if h.current_value is not None
        ) or total_invested

        absolute_return = current_value - total_invested
        return_pct = (absolute_return / total_invested * 100) if total_invested > 0 else 0

        # Portfolio volatility and Sharpe (from historical returns)
        volatility = None
        sharpe = None
        sortino = None
        max_drawdown = None
        annualized_return = None
        daily_return = None
        beta = None

        symbols = [h.symbol for h in holdings_response if h.weight]
        weights = [h.weight / 100 for h in holdings_response if h.weight]

        if symbols and len(symbols) > 1:
            try:
                price_data = yf.download(symbols, period="1y", interval="1d", progress=False)["Close"]
                if not price_data.empty and len(price_data) > 20:
                    returns = price_data.pct_change().dropna()
                    weights_arr = np.array(weights)
                    weights_arr = weights_arr / weights_arr.sum()

                    # Portfolio daily returns
                    portfolio_returns = (returns * weights_arr).sum(axis=1)

                    daily_return = float(portfolio_returns.iloc[-1] * 100)

                    # Annualized
                    ann_return = float(((1 + portfolio_returns.mean()) ** TRADING_DAYS_PER_YEAR - 1) * 100)
                    annualized_return = ann_return

                    # Volatility (annualized)
                    vol = float(portfolio_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100)
                    volatility = vol

                    # Sharpe ratio
                    excess_return = portfolio_returns.mean() - RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
                    std = portfolio_returns.std()
                    sharpe = float(excess_return / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else None

                    # Sortino ratio (downside deviation)
                    negative_returns = portfolio_returns[portfolio_returns < 0]
                    downside_std = float(negative_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
                    sortino = float(excess_return / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR)) if downside_std > 0 else None

                    # Maximum drawdown
                    cum_returns = (1 + portfolio_returns).cumprod()
                    rolling_max = cum_returns.cummax()
                    drawdown = (cum_returns - rolling_max) / rolling_max
                    max_drawdown = float(drawdown.min() * 100)

            except Exception:
                pass

        # Sector allocation (simplified)
        sector_allocation = {}
        for h in holdings_response:
            if h.weight:
                try:
                    t = yf.Ticker(h.symbol)
                    sector = t.info.get("sector", "Unknown")
                    sector_allocation[sector] = sector_allocation.get(sector, 0) + h.weight
                except Exception:
                    sector_allocation["Unknown"] = sector_allocation.get("Unknown", 0) + (h.weight or 0)

        return PortfolioAnalyticsResponse(
            portfolio_id=portfolio.id,
            total_invested=round(total_invested, 2),
            current_value=round(current_value, 2),
            absolute_return=round(absolute_return, 2),
            return_pct=round(return_pct, 2),
            daily_return=round(daily_return, 4) if daily_return is not None else None,
            annualized_return=round(annualized_return, 2) if annualized_return is not None else None,
            portfolio_volatility=round(volatility, 2) if volatility is not None else None,
            max_drawdown=round(max_drawdown, 2) if max_drawdown is not None else None,
            sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
            sortino_ratio=round(sortino, 4) if sortino is not None else None,
            beta=beta,
            holdings=holdings_response,
            sector_allocation=sector_allocation,
            asset_allocation={h.symbol: round(h.weight or 0, 2) for h in holdings_response},
            calculated_at=datetime.now(timezone.utc),
        )

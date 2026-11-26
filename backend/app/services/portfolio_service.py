"""
FinSight AI — Portfolio Service

* Holdings are derived from the transaction ledger (average-cost method), so the
  positions table can always be rebuilt and never drifts from the transactions.
* Analytics use one year of daily closes and the *current* weights
  (constant-weight assumption, rebalanced daily).

Formulas (r = daily portfolio returns, 252 trading days per year):
  Annualized return  = (∏(1 + r))^(252 / n) − 1
  Volatility         = σ(r) · √252
  Sharpe ratio       = (mean(r) − r_f/252) / σ(r) · √252
  Sortino ratio      = (mean(r) − r_f/252) / DD · √252, DD = √mean(min(r, 0)²)
  Max drawdown       = min_t (V_t / max_{s≤t} V_s − 1)
  Beta               = Cov(r, r_m) / Var(r_m)   (market = S&P 500)
  VaR 95% (1-day)    = −Q_5%(r) · value        (historical simulation)
  CVaR 95% (1-day)   = −E[r | r ≤ Q_5%(r)] · value
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import market_data as md
from app.models import Portfolio, PortfolioHolding, PortfolioTransaction
from app.schemas.portfolio import AddTransactionRequest, HoldingResponse, PortfolioAnalyticsResponse
from app.services.stock_service import StockService

TRADING_DAYS = 252
RISK_FREE_RATE = 0.05
BENCHMARK = "^GSPC"
EPS = 1e-9


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC so comparisons never fail."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def replay_transactions(transactions: List[PortfolioTransaction]) -> Tuple[Dict[str, dict], float]:
    """Rebuild positions from the ledger. Returns ({symbol: {quantity, avg_cost}}, realized_pnl).

    Raises ValueError if a SELL exceeds the quantity held at that point in time.
    """
    positions: Dict[str, dict] = {}
    realized = 0.0
    ordered = sorted(transactions, key=lambda t: (_aware(t.transaction_date), _aware(t.created_at or t.transaction_date)))
    for t in ordered:
        qty, price, fees = float(t.quantity), float(t.price), float(t.fees or 0)
        pos = positions.setdefault(t.symbol, {"quantity": 0.0, "avg_cost": 0.0})
        if t.transaction_type == "BUY":
            new_qty = pos["quantity"] + qty
            pos["avg_cost"] = (pos["quantity"] * pos["avg_cost"] + qty * price + fees) / new_qty
            pos["quantity"] = new_qty
        else:
            if qty > pos["quantity"] + EPS:
                raise ValueError(f"Cannot sell {qty:g} {t.symbol}: only {pos['quantity']:g} held on {t.transaction_date.date()}")
            realized += (price - pos["avg_cost"]) * qty - fees
            pos["quantity"] -= qty
            if pos["quantity"] <= EPS:
                positions.pop(t.symbol)
    return positions, realized


class PortfolioService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stocks = StockService()

    async def _transactions(self, portfolio_id: str) -> List[PortfolioTransaction]:
        result = await self.db.execute(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio_id))
        return list(result.scalars().all())

    async def rebuild_holdings(self, portfolio: Portfolio, transactions: Optional[List[PortfolioTransaction]] = None) -> float:
        txns = transactions if transactions is not None else await self._transactions(portfolio.id)
        positions, realized = replay_transactions(txns)
        await self.db.execute(delete(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id))
        for symbol, pos in positions.items():
            self.db.add(PortfolioHolding(
                id=str(uuid.uuid4()), portfolio_id=portfolio.id, symbol=symbol,
                quantity=round(pos["quantity"], 6), avg_purchase_price=round(pos["avg_cost"], 4),
                currency=portfolio.currency,
            ))
        return realized

    async def add_transaction(self, portfolio: Portfolio, payload: AddTransactionRequest) -> dict:
        symbol = payload.symbol.upper()
        if payload.transaction_type.upper() == "BUY":
            quote = await md.aquotes([symbol])
            if symbol not in quote:
                raise HTTPException(status_code=400, detail=f"Unknown symbol '{symbol}' — no market data found")

        txn = PortfolioTransaction(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio.id,
            symbol=symbol,
            transaction_type=payload.transaction_type.upper(),
            quantity=payload.quantity,
            price=payload.price,
            fees=payload.fees,
            transaction_date=payload.transaction_date or datetime.now(timezone.utc),
            notes=payload.notes,
            created_at=datetime.now(timezone.utc),
        )
        existing = await self._transactions(portfolio.id)
        try:
            await self.rebuild_holdings(portfolio, existing + [txn])
        except ValueError as exc:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        self.db.add(txn)
        await self.db.commit()
        return {"message": "Transaction recorded", "transaction_id": txn.id}

    async def delete_transaction(self, portfolio: Portfolio, txn_id: str) -> None:
        txns = await self._transactions(portfolio.id)
        target = next((t for t in txns if t.id == txn_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Transaction not found")
        remaining = [t for t in txns if t.id != txn_id]
        try:
            await self.rebuild_holdings(portfolio, remaining)
        except ValueError as exc:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail=f"Deleting this transaction would leave an invalid ledger: {exc}")
        await self.db.delete(target)
        await self.db.commit()

    async def _profiles(self, symbols: List[str]) -> Dict[str, dict]:
        return await self.stocks.get_profiles(symbols)

    async def get_holdings_with_prices(self, portfolio_id: str) -> List[HoldingResponse]:
        result = await self.db.execute(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id))
        holdings = list(result.scalars().all())
        if not holdings:
            return []

        symbols = [h.symbol for h in holdings]
        quotes, profiles = await asyncio.gather(md.aquotes(symbols), self._profiles(symbols))

        values = {h.symbol: float(h.quantity) * (quotes.get(h.symbol, {}).get("price") or float(h.avg_purchase_price)) for h in holdings}
        total_value = sum(values.values())

        out = []
        for h in holdings:
            q = quotes.get(h.symbol)
            qty, avg = float(h.quantity), float(h.avg_purchase_price)
            cost = qty * avg
            price = q["price"] if q else None
            value = qty * price if price is not None else None
            pnl = value - cost if value is not None else None
            out.append(HoldingResponse(
                id=h.id,
                symbol=h.symbol,
                name=profiles.get(h.symbol, {}).get("name"),
                sector=profiles.get(h.symbol, {}).get("sector"),
                quantity=qty,
                avg_purchase_price=round(avg, 4),
                cost_basis=round(cost, 2),
                current_price=round(price, 4) if price is not None else None,
                current_value=round(value, 2) if value is not None else None,
                day_change_pct=q["change_pct"] if q else None,
                unrealized_pnl=round(pnl, 2) if pnl is not None else None,
                unrealized_pnl_pct=round(pnl / cost * 100, 2) if pnl is not None and cost else None,
                weight=round(values[h.symbol] / total_value * 100, 2) if total_value > 0 else None,
                is_demo=bool(q and q["is_demo"]),
            ))
        out.sort(key=lambda x: x.current_value or 0, reverse=True)
        return out

    async def compute_analytics(self, portfolio: Portfolio) -> PortfolioAnalyticsResponse:
        holdings = await self.get_holdings_with_prices(portfolio.id)
        _, realized = replay_transactions(await self._transactions(portfolio.id))

        total_invested = sum(h.cost_basis for h in holdings)
        current_value = sum(h.current_value if h.current_value is not None else h.cost_basis for h in holdings)
        absolute_return = current_value - total_invested
        metrics: dict = {}
        performance: List[dict] = []

        weighted = [(h.symbol, (h.weight or 0) / 100) for h in holdings if h.weight]
        if weighted:
            symbols = [s for s, _ in weighted]
            try:
                prices, _ = await md.acloses(symbols + [BENCHMARK], period="1y")
                metrics, performance = self._risk_metrics(prices, dict(weighted), current_value)
            except md.MarketDataError:
                pass

        sectors: Dict[str, float] = {}
        for h in holdings:
            if h.weight:
                sectors[h.sector or "Other"] = round(sectors.get(h.sector or "Other", 0) + h.weight, 2)

        return PortfolioAnalyticsResponse(
            portfolio_id=portfolio.id,
            total_invested=round(total_invested, 2),
            current_value=round(current_value, 2),
            absolute_return=round(absolute_return, 2),
            return_pct=round(absolute_return / total_invested * 100, 2) if total_invested > 0 else 0.0,
            realized_pnl=round(realized, 2),
            holdings=holdings,
            sector_allocation=dict(sorted(sectors.items(), key=lambda kv: -kv[1])),
            asset_allocation={h.symbol: h.weight or 0 for h in holdings},
            performance=performance,
            methodology="Risk metrics use 1 year of daily closes with current weights held constant; risk-free rate 5%; VaR/CVaR by historical simulation.",
            is_demo=any(h.is_demo for h in holdings),
            calculated_at=datetime.now(timezone.utc),
            **metrics,
        )

    @staticmethod
    def _risk_metrics(prices: pd.DataFrame, weights: Dict[str, float], value: float) -> Tuple[dict, List[dict]]:
        cols = [s for s in weights if s in prices.columns]
        if not cols:
            return {}, []
        asset_returns = prices[cols].pct_change().dropna(how="any")
        if len(asset_returns) < 20:
            return {}, []
        w = np.array([weights[s] for s in cols])
        w = w / w.sum()
        r = asset_returns.values @ w
        r_series = pd.Series(r, index=asset_returns.index)

        n = len(r)
        mean, std = r.mean(), r.std(ddof=1)
        rf_daily = RISK_FREE_RATE / TRADING_DAYS
        downside = np.sqrt(np.mean(np.minimum(r, 0) ** 2))
        cumulative = np.cumprod(1 + r)
        drawdown = cumulative / np.maximum.accumulate(cumulative) - 1
        q05 = np.percentile(r, 5)

        metrics = {
            "daily_return": round(float(r[-1] * 100), 4),
            "annualized_return": round(float((cumulative[-1] ** (TRADING_DAYS / n) - 1) * 100), 2),
            "portfolio_volatility": round(float(std * np.sqrt(TRADING_DAYS) * 100), 2),
            "sharpe_ratio": round(float((mean - rf_daily) / std * np.sqrt(TRADING_DAYS)), 4) if std > 0 else None,
            "sortino_ratio": round(float((mean - rf_daily) / downside * np.sqrt(TRADING_DAYS)), 4) if downside > 0 else None,
            "max_drawdown": round(float(drawdown.min() * 100), 2),
            "var_95": round(float(-q05 * value), 2),
            "cvar_95": round(float(-r[r <= q05].mean() * value), 2),
        }

        performance: List[dict] = []
        if BENCHMARK in prices.columns:
            bench = prices[BENCHMARK].pct_change().reindex(asset_returns.index).fillna(0)
            if bench.var() > 0:
                metrics["beta"] = round(float(np.cov(r, bench.values, ddof=1)[0, 1] / bench.var(ddof=1)), 3)
            metrics["benchmark_return"] = round(float(((1 + bench).prod() - 1) * 100), 2)
            port_idx = (1 + r_series).cumprod() * 100
            bench_idx = (1 + bench).cumprod() * 100
            step = max(1, n // 120)
            for i in list(range(0, n, step)) + ([n - 1] if (n - 1) % step else []):
                performance.append({
                    "date": str(r_series.index[i].date()),
                    "portfolio": round(float(port_idx.iloc[i]), 2),
                    "benchmark": round(float(bench_idx.iloc[i]), 2),
                })
        return metrics, performance

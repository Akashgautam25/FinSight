"""
FinSight AI — Demo data seeder

Creates (or re-creates) the demo account `demo@finsight.ai` / `FinSight2026!` with a
portfolio whose trades are priced at real historical closes, a watchlist, price alerts
and a welcome notification. Used by `scripts/seed_db.py` / `make seed`, and run
automatically at startup when SEED_DEMO_ON_STARTUP=true (online deployments whose
database resets on every restart).
"""

import asyncio
import uuid
from datetime import timezone

import pandas as pd
from sqlalchemy import select

from app.data import market_data as md
from app.database import AsyncSessionLocal, create_tables
from app.models import (
    Notification, Portfolio, PortfolioTransaction, PriceAlert, User, UserPreferences,
    UserProfile, Watchlist, WatchlistStock,
)
from app.services.portfolio_service import PortfolioService
from app.utils.auth_utils import hash_password

DEMO_EMAIL = "demo@finsight.ai"
DEMO_PASSWORD = "FinSight2026!"

# (symbol, type, quantity, trading days ago)
TRADES = [
    ("AAPL", "BUY", 25, 240), ("MSFT", "BUY", 12, 230), ("NVDA", "BUY", 40, 220),
    ("JPM", "BUY", 15, 200), ("KO", "BUY", 30, 180), ("GOOGL", "BUY", 20, 150),
    ("NVDA", "SELL", 10, 90), ("AAPL", "BUY", 10, 60), ("XOM", "BUY", 18, 40),
]
WATCHLIST = ["AAPL", "NVDA", "TSLA", "AMZN", "META", "RELIANCE.NS", "TCS.NS"]


def _close_on(symbol: str, days_ago: int) -> tuple:
    df, _ = md.history(symbol, "2y", "1d")
    row = df.iloc[-(days_ago + 1)]
    when = pd.Timestamp(df.index[-(days_ago + 1)]).to_pydatetime().replace(hour=15, tzinfo=timezone.utc)
    return round(float(row["Close"]), 2), when


async def seed() -> str:
    await create_tables()
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
        if existing:
            await db.delete(existing)
            await db.commit()

        user = User(id=str(uuid.uuid4()), email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD), is_verified=True)
        db.add(user)
        db.add(UserProfile(id=str(uuid.uuid4()), user_id=user.id, full_name="Alex Mercer",
                           bio="Final-year CS & AI student exploring quantitative investing.", default_currency="USD"))
        db.add(UserPreferences(id=str(uuid.uuid4()), user_id=user.id, theme="dark", default_market="US"))

        portfolio = Portfolio(id=str(uuid.uuid4()), user_id=user.id, name="Core Growth Portfolio",
                              description="Diversified large-cap portfolio used for the FinSight demo.", currency="USD", is_default=True)
        db.add(portfolio)
        txns = []
        for symbol, kind, qty, days_ago in TRADES:
            price, when = await asyncio.to_thread(_close_on, symbol, days_ago)
            txns.append(PortfolioTransaction(
                id=str(uuid.uuid4()), portfolio_id=portfolio.id, symbol=symbol, transaction_type=kind,
                quantity=qty, price=price, fees=1.0, transaction_date=when, created_at=when,
                notes="Seeded demo trade",
            ))
        for t in txns:
            db.add(t)
        await db.flush()
        await PortfolioService(db).rebuild_holdings(portfolio, txns)

        wl = Watchlist(id=str(uuid.uuid4()), user_id=user.id, name="Tech & India Leaders", is_default=True)
        db.add(wl)
        for i, sym in enumerate(WATCHLIST):
            db.add(WatchlistStock(id=str(uuid.uuid4()), watchlist_id=wl.id, symbol=sym, sort_order=i))

        quotes = await md.aquotes(["AAPL", "TSLA"])
        if "AAPL" in quotes:
            db.add(PriceAlert(id=str(uuid.uuid4()), user_id=user.id, symbol="AAPL", alert_type="price_above",
                              target_value=round(quotes["AAPL"]["price"] * 1.05, 2), condition="above"))
        if "TSLA" in quotes:
            db.add(PriceAlert(id=str(uuid.uuid4()), user_id=user.id, symbol="TSLA", alert_type="price_below",
                              target_value=round(quotes["TSLA"]["price"] * 0.9, 2), condition="below"))
        db.add(Notification(id=str(uuid.uuid4()), user_id=user.id, type="welcome", title="Welcome to FinSight AI",
                            message="Your demo portfolio, watchlist and alerts are ready. Try the AI Assistant or train a model on the Predictions page.",
                            payload={"link": "/overview"}))
        await db.commit()

    # Pre-load company profiles (security master) so the first dashboard load is fast
    from app.services.stock_service import StockService
    await StockService().get_profiles(sorted({t[0] for t in TRADES} | set(WATCHLIST)))

    data_mode = "simulated" if (await md.aquotes(["AAPL"])).get("AAPL", {}).get("is_demo") else "live"
    return f"Demo account ready ({data_mode} prices): {DEMO_EMAIL} / {DEMO_PASSWORD}"



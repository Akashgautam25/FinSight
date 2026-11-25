"""
FinSight AI — Database Seeding Script
Populates initial sample users, portfolios, transactions, watchlists, and demo holdings.
Run with: python infrastructure/scripts/seed_db.py
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from passlib.context import CryptContext

# Import database models
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend")))

from app.models import (
    Base, User, UserProfile, UserPreferences,
    Portfolio, PortfolioHolding, PortfolioTransaction,
    Watchlist, WatchlistStock, Stock, FinancialMetrics
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://finsight:password@localhost:5432/finsight_db"
)


async def seed():
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        # 1. Create Default Demo User
        user_id = str(uuid.uuid4())
        demo_user = User(
            id=user_id,
            email="demo@finsight.ai",
            hashed_password=pwd_context.hash("FinSight2026!"),
            is_active=True,
            is_verified=True,
            role="user"
        )
        session.add(demo_user)

        profile = UserProfile(
            id=str(uuid.uuid4()),
            user_id=user_id,
            full_name="Alex Mercer",
            bio="Quantitative analyst & active equity investor.",
            default_currency="USD",
            timezone="America/New_York"
        )
        session.add(profile)

        pref = UserPreferences(
            id=str(uuid.uuid4()),
            user_id=user_id,
            theme="dark",
            default_market="US",
            dashboard_layout={"columns": 3}
        )
        session.add(pref)

        # 2. Create Sample Portfolio
        port_id = str(uuid.uuid4())
        portfolio = Portfolio(
            id=port_id,
            user_id=user_id,
            name="Core Technology & Growth",
            description="Long-term diversified high-conviction tech and innovation holdings.",
            currency="USD",
            is_default=True
        )
        session.add(portfolio)

        # Add initial holdings
        sample_holdings = [
            ("AAPL", 50, 182.40),
            ("NVDA", 80, 115.50),
            ("MSFT", 30, 395.00),
            ("GOOGL", 40, 155.20),
        ]

        for sym, qty, avg_price in sample_holdings:
            holding = PortfolioHolding(
                id=str(uuid.uuid4()),
                portfolio_id=port_id,
                symbol=sym,
                quantity=qty,
                avg_purchase_price=avg_price,
                currency="USD"
            )
            session.add(holding)

            txn = PortfolioTransaction(
                id=str(uuid.uuid4()),
                portfolio_id=port_id,
                symbol=sym,
                transaction_type="BUY",
                quantity=qty,
                price=avg_price,
                fees=0.0,
                transaction_date=datetime.now(timezone.utc) - timedelta(days=90),
                notes="Initial portfolio funding allocation."
            )
            session.add(txn)

        # 3. Create Sample Watchlist
        wl_id = str(uuid.uuid4())
        watchlist = Watchlist(
            id=wl_id,
            user_id=user_id,
            name="Mega-Cap Leaders",
            is_default=True
        )
        session.add(watchlist)

        for idx, sym in enumerate(["AAPL", "NVDA", "MSFT", "AMZN", "TSLA"]):
            w_stock = WatchlistStock(
                id=str(uuid.uuid4()),
                watchlist_id=wl_id,
                symbol=sym,
                sort_order=idx
            )
            session.add(w_stock)

        await session.commit()
        print("Database seeded successfully with default user demo@finsight.ai / FinSight2026!")


if __name__ == "__main__":
    asyncio.run(seed())

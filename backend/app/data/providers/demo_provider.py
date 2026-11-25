"""
FinSight AI — Offline / Fallback Demo Data Provider
Provides realistic, calibrated mock financial data when external APIs (yfinance, Finnhub, Alpha Vantage)
are offline, unreachable, or rate-limited.
CRITICAL: Every payload is transparently flagged with `is_demo=True` to never deceive the user.
"""

from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import numpy as np


DEMO_STOCKS = {
    "AAPL": {
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "currency": "USD",
        "base_price": 228.50,
        "market_cap": 3480000000000,
        "pe_ratio": 33.4,
        "eps": 6.84,
        "beta": 1.08,
        "dividend_yield": 0.0044,
        "week_52_high": 237.23,
        "week_52_low": 164.08,
        "roe": 1.47,
        "roa": 0.28,
        "debt_to_equity": 1.45,
        "profit_margin": 0.24,
        "revenue_growth": 0.06,
        "free_cash_flow": 108000000000,
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "United States",
        "currency": "USD",
        "base_price": 141.20,
        "market_cap": 3460000000000,
        "pe_ratio": 55.2,
        "eps": 2.56,
        "beta": 1.68,
        "dividend_yield": 0.0003,
        "week_52_high": 149.77,
        "week_52_low": 45.11,
        "roe": 1.15,
        "roa": 0.58,
        "debt_to_equity": 0.17,
        "profit_margin": 0.55,
        "revenue_growth": 1.22,
        "free_cash_flow": 39000000000,
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "country": "United States",
        "currency": "USD",
        "base_price": 418.00,
        "market_cap": 3120000000000,
        "pe_ratio": 35.8,
        "eps": 11.67,
        "beta": 0.89,
        "dividend_yield": 0.0072,
        "week_52_high": 468.35,
        "week_52_low": 366.50,
        "roe": 0.39,
        "roa": 0.19,
        "debt_to_equity": 0.42,
        "profit_margin": 0.36,
        "revenue_growth": 0.15,
        "free_cash_flow": 74000000000,
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "industry": "Internet Content & Information",
        "country": "United States",
        "currency": "USD",
        "base_price": 175.50,
        "market_cap": 2180000000000,
        "pe_ratio": 23.5,
        "eps": 7.47,
        "beta": 1.05,
        "dividend_yield": 0.0045,
        "week_52_high": 191.75,
        "week_52_low": 120.21,
        "roe": 0.31,
        "roa": 0.18,
        "debt_to_equity": 0.11,
        "profit_margin": 0.27,
        "revenue_growth": 0.14,
        "free_cash_flow": 69000000000,
    },
}


class DemoDataProvider:
    """Generates synthetic geometric Brownian motion time series and fundamental metrics."""

    @staticmethod
    def get_stock_detail(symbol: str) -> Optional[dict]:
        meta = DEMO_STOCKS.get(symbol.upper())
        if not meta:
            # Generate pseudo data for arbitrary unknown symbol
            meta = {
                "name": f"{symbol.upper()} Corp",
                "exchange": "NYSE",
                "sector": "Diversified",
                "industry": "General",
                "country": "United States",
                "currency": "USD",
                "base_price": 100.0,
                "market_cap": 50000000000,
                "pe_ratio": 20.0,
                "eps": 5.0,
                "beta": 1.0,
                "dividend_yield": 0.015,
                "week_52_high": 125.0,
                "week_52_low": 85.0,
                "roe": 0.15,
                "roa": 0.08,
                "debt_to_equity": 0.5,
                "profit_margin": 0.12,
                "revenue_growth": 0.08,
                "free_cash_flow": 2000000000,
            }

        prev_close = round(meta["base_price"] * (1 + np.random.uniform(-0.02, 0.02)), 2)
        current_price = meta["base_price"]

        return {
            "symbol": symbol.upper(),
            "name": meta["name"],
            "exchange": meta["exchange"],
            "sector": meta["sector"],
            "industry": meta["industry"],
            "country": meta["country"],
            "currency": meta["currency"],
            "current_price": current_price,
            "previous_close": prev_close,
            "day_high": round(current_price * 1.015, 2),
            "day_low": round(current_price * 0.985, 2),
            "volume": int(np.random.randint(15_000_000, 60_000_000)),
            "metrics": {
                "symbol": symbol.upper(),
                "market_cap": meta["market_cap"],
                "pe_ratio": meta["pe_ratio"],
                "eps": meta["eps"],
                "dividend_yield": meta["dividend_yield"],
                "beta": meta["beta"],
                "roe": meta["roe"],
                "roa": meta["roa"],
                "debt_to_equity": meta["debt_to_equity"],
                "profit_margin": meta["profit_margin"],
                "revenue_growth": meta["revenue_growth"],
                "free_cash_flow": meta["free_cash_flow"],
                "week_52_high": meta["week_52_high"],
                "week_52_low": meta["week_52_low"],
                "extra_metrics": {"is_simulated": True},
                "as_of_date": str(datetime.now(timezone.utc).date()),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "data_source": "demo_calibrated_simulation",
            "is_delayed": True,
            "is_demo": True,
        }

    @staticmethod
    def get_history(symbol: str, days: int = 252) -> dict:
        """Simulate geometric Brownian motion price series."""
        np.random.seed(sum(ord(c) for c in symbol))
        base_price = DEMO_STOCKS.get(symbol.upper(), {}).get("base_price", 100.0)

        dt = 1 / 252
        mu = 0.12  # 12% drift
        sigma = 0.22  # 22% annual volatility

        # Geometric Brownian motion
        daily_returns = np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * np.random.normal(0, 1, days))
        prices = np.cumprod(daily_returns) * (base_price * 0.85)

        end_date = datetime.now(timezone.utc).date()
        date_list = [end_date - timedelta(days=(days - i)) for i in range(days)]

        data = []
        for i, d in enumerate(date_list):
            close_p = round(float(prices[i]), 2)
            open_p = round(close_p * (1 + np.random.uniform(-0.005, 0.005)), 2)
            high_p = round(max(open_p, close_p) * (1 + abs(np.random.uniform(0.001, 0.015))), 2)
            low_p = round(min(open_p, close_p) * (1 - abs(np.random.uniform(0.001, 0.015))), 2)
            vol = int(np.random.randint(10_000_000, 50_000_000))
            data.append({
                "date": str(d),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
            })

        return {
            "symbol": symbol.upper(),
            "period": "1y",
            "interval": "1d",
            "data": data,
            "data_points": len(data),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_delayed": True,
            "is_demo": True,
            "disclaimer": "SIMULATED CALIBRATED DEMO DATA: Real external APIs currently unreachable.",
        }

"""
FinSight AI — Offline / Fallback Demo Data Provider

Generates realistic, *deterministic* market data when live sources (Yahoo Finance)
are unreachable or rate-limited, so every feature keeps working during offline demos.

* Prices follow geometric Brownian motion calibrated per stock (drift + volatility).
* The same symbol always produces the same series (seeded by the ticker), and the
  latest close equals the stock's reference price, so detail pages, charts,
  portfolios and ML models all agree with each other.
* Fundamentals are approximate reference values for illustration only.

CRITICAL: every payload built from this module is flagged ``is_demo=True`` and the
UI labels it "Simulated data" — it is never presented as real market data.
"""

from __future__ import annotations

import zlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# name, exchange, sector, industry, country, currency, price, market_cap, pe, eps,
# beta, dividend_yield, roe, roa, debt_to_equity, profit_margin, revenue_growth,
# free_cash_flow, annual_volatility, annual_drift
_RAW = [
    ("AAPL", "Apple Inc.", "NASDAQ", "Technology", "Consumer Electronics", "United States", "USD", 228.5, 3.48e12, 33.4, 6.84, 1.08, 0.0044, 1.47, 0.28, 1.45, 0.24, 0.06, 1.08e11, 0.24, 0.14),
    ("MSFT", "Microsoft Corporation", "NASDAQ", "Technology", "Software - Infrastructure", "United States", "USD", 418.0, 3.12e12, 35.8, 11.67, 0.89, 0.0072, 0.39, 0.19, 0.42, 0.36, 0.15, 7.4e10, 0.22, 0.15),
    ("NVDA", "NVIDIA Corporation", "NASDAQ", "Technology", "Semiconductors", "United States", "USD", 141.2, 3.46e12, 55.2, 2.56, 1.68, 0.0003, 1.15, 0.58, 0.17, 0.55, 1.22, 3.9e10, 0.48, 0.35),
    ("GOOGL", "Alphabet Inc.", "NASDAQ", "Communication Services", "Internet Content & Information", "United States", "USD", 175.5, 2.18e12, 23.5, 7.47, 1.05, 0.0045, 0.31, 0.18, 0.11, 0.27, 0.14, 6.9e10, 0.27, 0.13),
    ("AMZN", "Amazon.com, Inc.", "NASDAQ", "Consumer Cyclical", "Internet Retail", "United States", "USD", 198.4, 2.08e12, 42.1, 4.71, 1.15, 0.0, 0.22, 0.08, 0.54, 0.08, 0.11, 4.7e10, 0.30, 0.16),
    ("META", "Meta Platforms, Inc.", "NASDAQ", "Communication Services", "Internet Content & Information", "United States", "USD", 565.0, 1.43e12, 27.0, 20.9, 1.21, 0.0035, 0.36, 0.22, 0.27, 0.36, 0.22, 5.2e10, 0.35, 0.18),
    ("TSLA", "Tesla, Inc.", "NASDAQ", "Consumer Cyclical", "Auto Manufacturers", "United States", "USD", 342.1, 1.10e12, 94.0, 3.65, 2.30, 0.0, 0.21, 0.10, 0.18, 0.13, 0.02, 3.6e9, 0.55, 0.10),
    ("AMD", "Advanced Micro Devices, Inc.", "NASDAQ", "Technology", "Semiconductors", "United States", "USD", 138.6, 2.25e11, 120.0, 1.16, 1.65, 0.0, 0.04, 0.03, 0.05, 0.06, 0.18, 2.4e9, 0.45, 0.12),
    ("NFLX", "Netflix, Inc.", "NASDAQ", "Communication Services", "Entertainment", "United States", "USD", 875.0, 3.75e11, 48.5, 18.0, 1.27, 0.0, 0.35, 0.15, 0.71, 0.22, 0.15, 6.9e9, 0.33, 0.20),
    ("INTC", "Intel Corporation", "NASDAQ", "Technology", "Semiconductors", "United States", "USD", 24.1, 1.04e11, None, -3.9, 1.05, 0.0, -0.17, -0.09, 0.48, -0.36, -0.06, -1.5e10, 0.42, -0.05),
    ("JPM", "JPMorgan Chase & Co.", "NYSE", "Financial Services", "Banks - Diversified", "United States", "USD", 243.0, 6.85e11, 13.5, 18.0, 1.10, 0.0205, 0.17, 0.014, 1.30, 0.34, 0.12, 2.1e10, 0.21, 0.12),
    ("BAC", "Bank of America Corporation", "NYSE", "Financial Services", "Banks - Diversified", "United States", "USD", 46.5, 3.57e11, 16.9, 2.75, 1.33, 0.0224, 0.09, 0.008, 1.12, 0.26, 0.04, 1.8e10, 0.25, 0.09),
    ("V", "Visa Inc.", "NYSE", "Financial Services", "Credit Services", "United States", "USD", 312.0, 6.05e11, 32.0, 9.73, 0.95, 0.0075, 0.50, 0.21, 0.55, 0.55, 0.10, 1.9e10, 0.19, 0.13),
    ("JNJ", "Johnson & Johnson", "NYSE", "Healthcare", "Drug Manufacturers - General", "United States", "USD", 155.0, 3.73e11, 25.6, 6.05, 0.52, 0.0320, 0.21, 0.09, 0.44, 0.18, 0.04, 1.8e10, 0.15, 0.05),
    ("PFE", "Pfizer Inc.", "NYSE", "Healthcare", "Drug Manufacturers - General", "United States", "USD", 26.2, 1.48e11, 35.0, 0.75, 0.62, 0.0640, 0.04, 0.02, 0.73, 0.06, 0.02, 6.0e9, 0.24, -0.02),
    ("XOM", "Exxon Mobil Corporation", "NYSE", "Energy", "Oil & Gas Integrated", "United States", "USD", 118.0, 5.20e11, 14.6, 8.08, 0.88, 0.0330, 0.15, 0.08, 0.16, 0.10, -0.03, 3.3e10, 0.23, 0.06),
    ("WMT", "Walmart Inc.", "NYSE", "Consumer Defensive", "Discount Stores", "United States", "USD", 92.0, 7.40e11, 39.0, 2.36, 0.51, 0.0090, 0.21, 0.08, 0.68, 0.03, 0.05, 1.5e10, 0.17, 0.15),
    ("KO", "The Coca-Cola Company", "NYSE", "Consumer Defensive", "Beverages - Non-Alcoholic", "United States", "USD", 63.5, 2.74e11, 26.2, 2.42, 0.61, 0.0305, 0.40, 0.11, 1.62, 0.23, 0.03, 9.7e9, 0.14, 0.06),
    ("DIS", "The Walt Disney Company", "NYSE", "Communication Services", "Entertainment", "United States", "USD", 112.0, 2.03e11, 40.0, 2.80, 1.40, 0.0085, 0.05, 0.03, 0.42, 0.06, 0.04, 8.6e9, 0.28, 0.05),
    ("RELIANCE.NS", "Reliance Industries Limited", "NSE", "Energy", "Oil & Gas Refining & Marketing", "India", "INR", 1290.0, 1.75e13, 25.1, 51.4, 0.95, 0.0039, 0.09, 0.04, 0.37, 0.08, 0.07, 1.2e11, 0.24, 0.10),
    ("TCS.NS", "Tata Consultancy Services Limited", "NSE", "Technology", "Information Technology Services", "India", "INR", 4150.0, 1.50e13, 31.0, 134.0, 0.55, 0.0175, 0.52, 0.31, 0.09, 0.19, 0.06, 4.5e11, 0.20, 0.10),
    ("INFY.NS", "Infosys Limited", "NSE", "Technology", "Information Technology Services", "India", "INR", 1880.0, 7.80e12, 28.4, 66.2, 0.62, 0.0260, 0.31, 0.20, 0.09, 0.17, 0.03, 2.3e11, 0.22, 0.09),
    ("HDFCBANK.NS", "HDFC Bank Limited", "NSE", "Financial Services", "Banks - Regional", "India", "INR", 1740.0, 1.33e13, 19.5, 89.2, 0.78, 0.0110, 0.15, 0.019, 1.10, 0.25, 0.20, None, 0.20, 0.11),
]

_KEYS = [
    "symbol", "name", "exchange", "sector", "industry", "country", "currency", "base_price",
    "market_cap", "pe_ratio", "eps", "beta", "dividend_yield", "roe", "roa",
    "debt_to_equity", "profit_margin", "revenue_growth", "free_cash_flow", "volatility", "drift",
]

DEMO_STOCKS: Dict[str, dict] = {row[0]: dict(zip(_KEYS, row)) for row in _RAW}

DEMO_INDICES: Dict[str, dict] = {
    "^GSPC": {"name": "S&P 500", "base_price": 5970.0, "volatility": 0.15, "drift": 0.10, "currency": "USD"},
    "^DJI": {"name": "Dow Jones", "base_price": 44300.0, "volatility": 0.14, "drift": 0.08, "currency": "USD"},
    "^IXIC": {"name": "NASDAQ Composite", "base_price": 19100.0, "volatility": 0.20, "drift": 0.13, "currency": "USD"},
    "^NSEI": {"name": "NIFTY 50", "base_price": 24200.0, "volatility": 0.14, "drift": 0.11, "currency": "INR"},
    "^BSESN": {"name": "BSE SENSEX", "base_price": 79800.0, "volatility": 0.14, "drift": 0.11, "currency": "INR"},
}

PERIOD_DAYS = {
    "1d": 1, "5d": 5, "1mo": 22, "3mo": 64, "6mo": 127, "ytd": 0,
    "1y": 252, "2y": 504, "5y": 1260, "10y": 2520, "max": 2520,
}

INTRADAY_MINUTES = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30, "60m": 60, "90m": 90, "1h": 60}

_MAX_DAYS = 2520  # 10 years of trading days — the full simulated path


def _seed(symbol: str) -> int:
    return zlib.crc32(symbol.upper().encode("utf-8"))


def _meta(symbol: str) -> dict:
    sym = symbol.upper()
    if sym in DEMO_STOCKS:
        return DEMO_STOCKS[sym]
    if sym in DEMO_INDICES:
        return {"symbol": sym, **DEMO_INDICES[sym]}
    # Unknown ticker: plausible, deterministic placeholder values
    rng = np.random.default_rng(_seed(sym))
    price = float(np.round(rng.uniform(20, 400), 2))
    return {
        "symbol": sym, "name": f"{sym} (simulated)", "exchange": "N/A", "sector": "Unknown",
        "industry": "Unknown", "country": "Unknown", "currency": "INR" if sym.endswith((".NS", ".BO")) else "USD",
        "base_price": price, "market_cap": price * rng.uniform(2e8, 5e9), "pe_ratio": float(np.round(rng.uniform(10, 40), 1)),
        "eps": None, "beta": float(np.round(rng.uniform(0.6, 1.6), 2)), "dividend_yield": float(np.round(rng.uniform(0, 0.03), 4)),
        "roe": None, "roa": None, "debt_to_equity": None, "profit_margin": None, "revenue_growth": None,
        "free_cash_flow": None, "volatility": float(rng.uniform(0.18, 0.4)), "drift": float(rng.uniform(0.0, 0.15)),
    }


def is_known_symbol(symbol: str) -> bool:
    s = symbol.upper()
    return s in DEMO_STOCKS or s in DEMO_INDICES


def _business_days(end: pd.Timestamp, n: int) -> pd.DatetimeIndex:
    return pd.bdate_range(end=end, periods=n)


def _last_business_day() -> pd.Timestamp:
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    return today if today.weekday() < 5 else today - pd.offsets.BDay(1)


def _full_daily_path(symbol: str) -> pd.DataFrame:
    """Simulate the full 10-year daily OHLCV path (cached per symbol per day)."""
    end = _last_business_day()
    key = (symbol.upper(), end)
    cached = _PATH_CACHE.get(key)
    if cached is not None:
        return cached

    meta = _meta(symbol)
    rng = np.random.default_rng(_seed(symbol))
    sigma = float(meta.get("volatility") or 0.25)
    mu = float(meta.get("drift") or 0.08)
    dt = 1 / 252

    # GBM with mild volatility clustering for realism
    shocks = rng.standard_t(df=5, size=_MAX_DAYS) / np.sqrt(5 / 3)
    vol_regime = np.exp(0.25 * np.sin(np.linspace(0, 12 * np.pi, _MAX_DAYS) + rng.uniform(0, 6)))
    log_returns = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * shocks * vol_regime
    log_prices = np.cumsum(log_returns)
    closes = np.exp(log_prices - log_prices[-1]) * float(meta["base_price"])

    intraday_range = np.abs(rng.normal(0, sigma * np.sqrt(dt), _MAX_DAYS)) + 0.002
    opens = np.concatenate([[closes[0]], closes[:-1]]) * (1 + rng.normal(0, 0.003, _MAX_DAYS))
    highs = np.maximum(opens, closes) * (1 + intraday_range * rng.uniform(0.3, 1.0, _MAX_DAYS))
    lows = np.minimum(opens, closes) * (1 - intraday_range * rng.uniform(0.3, 1.0, _MAX_DAYS))

    base_volume = 5e7 if meta.get("market_cap", 0) and meta["market_cap"] > 1e12 else 1.5e7
    if symbol.startswith("^"):
        base_volume = 3e9
    volumes = (base_volume * np.exp(rng.normal(0, 0.35, _MAX_DAYS)) * (1 + 8 * np.abs(log_returns))).astype(np.int64)

    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=_business_days(end, _MAX_DAYS),
    ).round({"Open": 2, "High": 2, "Low": 2, "Close": 2})
    df.index.name = "Date"

    if len(_PATH_CACHE) > 200:
        _PATH_CACHE.clear()
    _PATH_CACHE[key] = df
    return df


_PATH_CACHE: Dict[tuple, pd.DataFrame] = {}


def _intraday(symbol: str, days: int, minutes: int) -> pd.DataFrame:
    daily = _full_daily_path(symbol).tail(days)
    rng = np.random.default_rng(_seed(symbol) + 7)
    frames = []
    bars_per_day = max(1, int(390 / minutes))
    for day, row in daily.iterrows():
        start = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30)
        idx = pd.date_range(start, periods=bars_per_day, freq=f"{minutes}min")
        # Brownian bridge from open to close for the session
        steps = rng.normal(0, 1, bars_per_day).cumsum()
        bridge = steps - np.linspace(0, 1, bars_per_day) * steps[-1]
        scale = (row["High"] - row["Low"]) / (np.ptp(bridge) + 1e-9) * 0.6
        path = np.linspace(row["Open"], row["Close"], bars_per_day) + bridge * scale
        close = np.round(path, 2)
        open_ = np.concatenate([[row["Open"]], close[:-1]])
        frames.append(pd.DataFrame({
            "Open": open_, "High": np.maximum(open_, close) * 1.0008, "Low": np.minimum(open_, close) * 0.9992,
            "Close": close, "Volume": (row["Volume"] / bars_per_day * rng.uniform(0.5, 1.5, bars_per_day)).astype(np.int64),
        }, index=idx))
    return pd.concat(frames).round(2) if frames else pd.DataFrame()


class DemoDataProvider:
    """Facade used by the market data layer when live data is unavailable."""

    @staticmethod
    def history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        if interval in INTRADAY_MINUTES:
            days = {"1d": 1, "5d": 5}.get(period, 5)
            return _intraday(symbol, days, INTRADAY_MINUTES[interval])

        full = _full_daily_path(symbol)
        if period == "ytd":
            start = pd.Timestamp(year=full.index[-1].year, month=1, day=1)
            df = full[full.index >= start]
        else:
            df = full.tail(PERIOD_DAYS.get(period, 252))

        if interval == "1wk":
            df = df.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
        elif interval == "1mo":
            df = df.resample("ME").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
        return df.copy()

    @staticmethod
    def info(symbol: str) -> dict:
        meta = _meta(symbol)
        full = _full_daily_path(symbol)
        last_year = full.tail(252)
        last, prev = full.iloc[-1], full.iloc[-2]
        return {
            "symbol": symbol.upper(),
            "longName": meta.get("name", symbol.upper()),
            "exchange": meta.get("exchange"),
            "sector": meta.get("sector"),
            "industry": meta.get("industry"),
            "country": meta.get("country"),
            "currency": meta.get("currency", "USD"),
            "currentPrice": float(last["Close"]),
            "previousClose": float(prev["Close"]),
            "dayHigh": float(last["High"]),
            "dayLow": float(last["Low"]),
            "volume": int(last["Volume"]),
            "marketCap": meta.get("market_cap"),
            "trailingPE": meta.get("pe_ratio"),
            "trailingEps": meta.get("eps"),
            "beta": meta.get("beta"),
            "dividendYield": meta.get("dividend_yield"),
            "returnOnEquity": meta.get("roe"),
            "returnOnAssets": meta.get("roa"),
            "debtToEquity": meta.get("debt_to_equity"),
            "profitMargins": meta.get("profit_margin"),
            "revenueGrowth": meta.get("revenue_growth"),
            "freeCashflow": meta.get("free_cash_flow"),
            "fiftyTwoWeekHigh": float(last_year["High"].max()),
            "fiftyTwoWeekLow": float(last_year["Low"].min()),
            "longBusinessSummary": f"{meta.get('name', symbol)} — simulated profile for offline demonstration.",
        }

    @staticmethod
    def search(query: str, limit: int = 10) -> List[dict]:
        q = query.strip().lower()
        results = []
        for sym, meta in DEMO_STOCKS.items():
            if q in sym.lower() or q in meta["name"].lower():
                results.append({
                    "symbol": sym, "name": meta["name"], "exchange": meta["exchange"],
                    "sector": meta["sector"], "industry": meta["industry"],
                    "country": meta["country"], "currency": meta["currency"],
                })
        results.sort(key=lambda r: (not r["symbol"].lower().startswith(q), r["symbol"]))
        return results[:limit]

    @staticmethod
    def news(symbol: Optional[str], limit: int = 10) -> List[dict]:
        """Illustrative headlines (clearly labelled as simulated)."""
        name = _meta(symbol)["name"] if symbol else "Global markets"
        templates = [
            ("{n} beats quarterly earnings expectations as revenue growth accelerates", "positive"),
            ("Analysts raise price target on {n} citing strong demand outlook", "positive"),
            ("{n} shares slip as investors weigh valuation concerns", "negative"),
            ("Regulators open review into {n} business practices", "negative"),
            ("{n} announces expanded share buyback programme", "positive"),
            ("{n} holds annual investor day, reiterates full-year guidance", "neutral"),
            ("Supply chain constraints could weigh on {n} margins, report says", "negative"),
            ("{n} launches new product line targeting enterprise customers", "positive"),
            ("Market volatility rises ahead of central bank decision", "neutral"),
            ("{n} trading volume spikes amid sector rotation", "neutral"),
        ]
        now = datetime.now(timezone.utc)
        rng = np.random.default_rng(_seed(symbol or "MARKET") + now.toordinal())
        order = rng.permutation(len(templates))
        items = []
        for rank, i in enumerate(order[:limit]):
            title, _ = templates[i]
            items.append({
                "id": f"demo-{(symbol or 'mkt').lower()}-{i}",
                "title": title.format(n=name),
                "summary": "Simulated headline generated for offline demonstration — not real news.",
                "url": "https://finance.yahoo.com/",
                "source": "FinSight Demo Feed",
                "author": None,
                "published_at": (now - timedelta(hours=int(rank * 5 + rng.integers(0, 4)))).isoformat(),
                "is_demo": True,
            })
        return items

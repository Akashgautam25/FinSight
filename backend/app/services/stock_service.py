"""
FinSight AI — Stock Service
Aggregates data from multiple providers with caching.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional, List

import yfinance as yf
import pandas as pd

from app.utils.cache import cache_get, cache_set
from app.schemas.stock import (
    StockDetailResponse, StockSearchResult, MarketOverviewResponse,
    TechnicalIndicatorsResponse, FinancialMetricsResponse,
)


MAJOR_INDICES = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "NASDAQ",
    "^NSEI": "NIFTY 50",
    "^BSESN": "BSE SENSEX",
}

CACHE_TTL = {
    "overview": 300,      # 5 min
    "detail": 180,        # 3 min
    "history": 600,       # 10 min
    "fundamentals": 1800, # 30 min
    "search": 86400,      # 1 day
}


class StockService:
    async def search(self, query: str, limit: int = 10) -> List[StockSearchResult]:
        """Search stocks using yfinance. Results cached 24h."""
        cache_key = f"search:{hashlib.md5(query.lower().encode()).hexdigest()}"
        cached = await cache_get(cache_key)
        if cached:
            return [StockSearchResult(**r) for r in cached[:limit]]

        try:
            # yfinance search
            tickers = yf.Tickers(query.upper())
            results = []

            # Try direct ticker first
            try:
                ticker = yf.Ticker(query.upper())
                info = ticker.info
                if info.get("symbol"):
                    results.append(StockSearchResult(
                        symbol=info.get("symbol", query.upper()),
                        name=info.get("longName") or info.get("shortName") or query,
                        exchange=info.get("exchange"),
                        sector=info.get("sector"),
                        industry=info.get("industry"),
                        country=info.get("country"),
                        currency=info.get("currency", "USD"),
                    ))
            except Exception:
                pass

            await cache_set(cache_key, [r.model_dump() for r in results], CACHE_TTL["search"])
            return results[:limit]
        except Exception as e:
            return []

    async def get_stock_detail(self, symbol: str) -> Optional[StockDetailResponse]:
        cache_key = f"stock:detail:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return StockDetailResponse(**cached)

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or not info.get("symbol"):
                return None

            # Get today's data
            hist = ticker.history(period="2d", interval="1d")
            current_price = None
            prev_close = None
            day_high = None
            day_low = None
            volume = None

            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else None
                day_high = float(hist["High"].iloc[-1])
                day_low = float(hist["Low"].iloc[-1])
                volume = int(hist["Volume"].iloc[-1])

            metrics = FinancialMetricsResponse(
                symbol=symbol,
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE") or info.get("forwardPE"),
                eps=info.get("trailingEps"),
                dividend_yield=info.get("dividendYield"),
                beta=info.get("beta"),
                roe=info.get("returnOnEquity"),
                roa=info.get("returnOnAssets"),
                debt_to_equity=info.get("debtToEquity"),
                profit_margin=info.get("profitMargins"),
                revenue_growth=info.get("revenueGrowth"),
                free_cash_flow=info.get("freeCashflow"),
                week_52_high=info.get("fiftyTwoWeekHigh"),
                week_52_low=info.get("fiftyTwoWeekLow"),
                extra_metrics={
                    "price_to_book": info.get("priceToBook"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "forward_pe": info.get("forwardPE"),
                    "peg_ratio": info.get("pegRatio"),
                    "current_ratio": info.get("currentRatio"),
                    "quick_ratio": info.get("quickRatio"),
                },
                as_of_date=datetime.now(timezone.utc).date(),
                fetched_at=datetime.now(timezone.utc),
            )

            result = StockDetailResponse(
                symbol=symbol,
                name=info.get("longName") or info.get("shortName") or symbol,
                exchange=info.get("exchange"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                country=info.get("country"),
                currency=info.get("currency", "USD"),
                current_price=current_price,
                previous_close=prev_close or info.get("previousClose"),
                day_high=day_high,
                day_low=day_low,
                volume=volume,
                metrics=metrics,
                last_updated=datetime.now(timezone.utc),
                is_delayed=True,
            )

            await cache_set(cache_key, result.model_dump(), CACHE_TTL["detail"])
            return result

        except Exception as e:
            return None

    async def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> dict:
        cache_key = f"stock:history:{symbol}:{period}:{interval}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                return {"symbol": symbol, "data": [], "is_demo": False}

            data = []
            for idx, row in hist.iterrows():
                data.append({
                    "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                    "open": round(float(row["Open"]), 4) if pd.notna(row["Open"]) else None,
                    "high": round(float(row["High"]), 4) if pd.notna(row["High"]) else None,
                    "low": round(float(row["Low"]), 4) if pd.notna(row["Low"]) else None,
                    "close": round(float(row["Close"]), 4) if pd.notna(row["Close"]) else None,
                    "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
                })

            result = {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "data": data,
                "data_points": len(data),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "is_delayed": True,
                "disclaimer": "Data may be delayed by 15–20 minutes on free data sources.",
            }

            await cache_set(cache_key, result, CACHE_TTL["history"])
            return result

        except Exception as e:
            return {"symbol": symbol, "data": [], "error": str(e), "is_demo": False}

    async def get_fundamentals(self, symbol: str) -> dict:
        cache_key = f"stock:fundamentals:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Income statement
            try:
                income = ticker.income_stmt
                income_data = income.to_dict() if income is not None and not income.empty else {}
            except Exception:
                income_data = {}

            # Balance sheet
            try:
                balance = ticker.balance_sheet
                balance_data = balance.to_dict() if balance is not None and not balance.empty else {}
            except Exception:
                balance_data = {}

            result = {
                "symbol": symbol,
                "info": {k: v for k, v in info.items() if v is not None},
                "income_statement_available": bool(income_data),
                "balance_sheet_available": bool(balance_data),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Financial data sourced from public filings via yfinance.",
            }

            await cache_set(cache_key, result, CACHE_TTL["fundamentals"])
            return result

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    async def get_technical_indicators(self, symbol: str) -> TechnicalIndicatorsResponse:
        import ta

        cache_key = f"stock:technical:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return TechnicalIndicatorsResponse(**cached)

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y", interval="1d")

            if hist.empty or len(hist) < 20:
                raise ValueError("Insufficient data for technical indicators")

            close = hist["Close"]
            high = hist["High"]
            low = hist["Low"]
            volume = hist["Volume"]

            # Moving Averages
            sma_20 = ta.trend.sma_indicator(close, window=20).iloc[-1]
            sma_50 = ta.trend.sma_indicator(close, window=50).iloc[-1]
            sma_200 = ta.trend.sma_indicator(close, window=200).iloc[-1] if len(hist) >= 200 else None
            ema_12 = ta.trend.ema_indicator(close, window=12).iloc[-1]
            ema_26 = ta.trend.ema_indicator(close, window=26).iloc[-1]

            # RSI
            rsi = ta.momentum.rsi(close, window=14).iloc[-1]

            # MACD
            macd_indicator = ta.trend.MACD(close)
            macd = macd_indicator.macd().iloc[-1]
            macd_signal = macd_indicator.macd_signal().iloc[-1]
            macd_hist = macd_indicator.macd_diff().iloc[-1]

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            bb_upper = bb.bollinger_hband().iloc[-1]
            bb_middle = bb.bollinger_mavg().iloc[-1]
            bb_lower = bb.bollinger_lband().iloc[-1]

            # ATR
            atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]

            def safe_float(val):
                try:
                    v = float(val)
                    return round(v, 4) if pd.notna(v) else None
                except Exception:
                    return None

            result = TechnicalIndicatorsResponse(
                symbol=symbol,
                date=hist.index[-1].date(),
                sma_20=safe_float(sma_20),
                sma_50=safe_float(sma_50),
                sma_200=safe_float(sma_200),
                ema_12=safe_float(ema_12),
                ema_26=safe_float(ema_26),
                rsi_14=safe_float(rsi),
                macd=safe_float(macd),
                macd_signal=safe_float(macd_signal),
                macd_hist=safe_float(macd_hist),
                bb_upper=safe_float(bb_upper),
                bb_middle=safe_float(bb_middle),
                bb_lower=safe_float(bb_lower),
                atr_14=safe_float(atr),
            )

            await cache_set(cache_key, result.model_dump(), 300)
            return result

        except Exception as e:
            raise ValueError(f"Failed to compute technical indicators: {e}")

    async def get_market_overview(self) -> MarketOverviewResponse:
        cache_key = "market:overview"
        cached = await cache_get(cache_key)
        if cached:
            return MarketOverviewResponse(**cached)

        try:
            indices = []
            for ticker_sym, name in MAJOR_INDICES.items():
                try:
                    t = yf.Ticker(ticker_sym)
                    hist = t.history(period="2d", interval="1d")
                    if not hist.empty:
                        last = float(hist["Close"].iloc[-1])
                        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last
                        chg = ((last - prev) / prev * 100) if prev else 0
                        indices.append({
                            "symbol": ticker_sym,
                            "name": name,
                            "value": round(last, 2),
                            "change_pct": round(chg, 2),
                        })
                except Exception:
                    pass

            result = MarketOverviewResponse(
                indices=indices,
                top_gainers=[],  # Populated from screener in production
                top_losers=[],
                most_active=[],
                market_status="delayed",
                as_of=datetime.now(timezone.utc),
            )

            await cache_set(cache_key, result.model_dump(), CACHE_TTL["overview"])
            return result

        except Exception as e:
            return MarketOverviewResponse(
                indices=[], top_gainers=[], top_losers=[],
                most_active=[], market_status="unavailable",
                as_of=datetime.now(timezone.utc),
            )

    async def compare_stocks(self, symbols: List[str], period: str = "1y") -> dict:
        results = {}
        for symbol in symbols:
            detail = await self.get_stock_detail(symbol)
            history = await self.get_history(symbol, period=period)
            results[symbol] = {
                "detail": detail.model_dump() if detail else None,
                "history": history.get("data", []),
            }
        return {
            "symbols": symbols,
            "period": period,
            "comparison": results,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

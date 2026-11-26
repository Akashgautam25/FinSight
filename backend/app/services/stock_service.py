"""
FinSight AI — Stock Service
Quotes, fundamentals, price history, technical indicators, market overview and
comparisons. Responses are cached; blocking I/O runs in worker threads.
"""

import hashlib
import math
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.data import market_data as md
from app.ml import indicators as ind
from app.schemas.stock import (
    FinancialMetricsResponse,
    IndicatorSignal,
    MarketOverviewResponse,
    StockDetailResponse,
    StockSearchResult,
    TechnicalIndicatorsResponse,
)
from app.utils.cache import cache_get, cache_set

MAJOR_INDICES = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "NASDAQ",
    "^NSEI": "NIFTY 50",
    "^BSESN": "BSE SENSEX",
}

# Universe scanned for top gainers / losers / most active
MOVERS_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "NFLX", "INTC",
    "JPM", "BAC", "V", "JNJ", "PFE", "XOM", "WMT", "KO", "DIS",
]

CACHE_TTL = {"overview": 300, "detail": 180, "history": 300, "technical": 300, "search": 3600}

VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max"}
VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo"}


def _f(value, digits: int = 4) -> Optional[float]:
    """Safe float conversion (NaN/inf/None → None)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, digits)


def us_market_status() -> str:
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return "closed"
    minutes = now.hour * 60 + now.minute
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "open"
    if 4 * 60 <= minutes < 9 * 60 + 30:
        return "pre-market"
    if 16 * 60 <= minutes < 20 * 60:
        return "after-hours"
    return "closed"


class StockService:
    # ── Search ───────────────────────────────────────────────────────────────
    async def search(self, query: str, limit: int = 10) -> List[StockSearchResult]:
        cache_key = f"search:{hashlib.md5(query.lower().encode()).hexdigest()}:{limit}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return [StockSearchResult(**r) for r in cached]

        results = await md.asearch(query, limit)
        parsed = [StockSearchResult(**r) for r in results if r.get("symbol")]
        await cache_set(cache_key, [r.model_dump() for r in parsed], CACHE_TTL["search"])
        return parsed

    # ── Detail ───────────────────────────────────────────────────────────────
    async def get_stock_detail(self, symbol: str) -> Optional[StockDetailResponse]:
        symbol = symbol.upper()
        cache_key = f"stock:detail:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return StockDetailResponse(**cached)

        try:
            info, is_demo = await md.ainfo(symbol)
        except md.MarketDataError:
            return None

        now = datetime.now(timezone.utc)
        price = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev = _f(info.get("previousClose") or info.get("regularMarketPreviousClose"))
        change = _f(price - prev) if price is not None and prev else None
        change_pct = _f((price - prev) / prev * 100, 2) if price is not None and prev else None

        dividend_yield = _f(info.get("dividendYield"), 6)
        # Yahoo switched dividendYield to percent units in 2025 (0.44 means 0.44%)
        if dividend_yield is not None and dividend_yield > 0.25:
            dividend_yield = round(dividend_yield / 100, 6)

        metrics = FinancialMetricsResponse(
            symbol=symbol,
            market_cap=_f(info.get("marketCap"), 0),
            pe_ratio=_f(info.get("trailingPE") or info.get("forwardPE"), 2),
            eps=_f(info.get("trailingEps"), 4),
            dividend_yield=dividend_yield,
            beta=_f(info.get("beta"), 3),
            roe=_f(info.get("returnOnEquity")),
            roa=_f(info.get("returnOnAssets")),
            # Yahoo reports debt-to-equity in percent (150 = 1.5x); simulated data is already a ratio
            debt_to_equity=_f(info["debtToEquity"] / (1 if is_demo else 100), 2) if info.get("debtToEquity") is not None else None,
            profit_margin=_f(info.get("profitMargins")),
            revenue_growth=_f(info.get("revenueGrowth")),
            free_cash_flow=_f(info.get("freeCashflow"), 0),
            week_52_high=_f(info.get("fiftyTwoWeekHigh"), 2),
            week_52_low=_f(info.get("fiftyTwoWeekLow"), 2),
            extra_metrics={
                "forward_pe": _f(info.get("forwardPE"), 2),
                "price_to_book": _f(info.get("priceToBook"), 2),
                "peg_ratio": _f(info.get("pegRatio") or info.get("trailingPegRatio"), 2),
                "enterprise_value": _f(info.get("enterpriseValue"), 0),
                "current_ratio": _f(info.get("currentRatio"), 2),
                "quick_ratio": _f(info.get("quickRatio"), 2),
                "employees": info.get("fullTimeEmployees"),
                "website": info.get("website"),
                "is_simulated": is_demo,
            },
            as_of_date=now.date(),
            fetched_at=now,
        )

        description = info.get("longBusinessSummary")
        result = StockDetailResponse(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName") or symbol,
            exchange=info.get("fullExchangeName") or info.get("exchange"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            country=info.get("country"),
            currency=info.get("currency") or "USD",
            description=description[:1200] if description else None,
            current_price=price,
            previous_close=prev,
            change=change,
            change_pct=change_pct,
            day_high=_f(info.get("dayHigh")),
            day_low=_f(info.get("dayLow")),
            volume=int(info["volume"]) if info.get("volume") else None,
            metrics=metrics,
            last_updated=now,
            data_source="simulated" if is_demo else "yahoo_finance",
            is_delayed=True,
            is_demo=is_demo,
        )
        await cache_set(cache_key, result.model_dump(mode="json"), CACHE_TTL["detail"])
        return result

    async def get_profile(self, symbol: str) -> dict:
        """Name / sector / currency for a ticker.

        Profiles rarely change, so they are persisted in the `stocks` table (the
        security master) and refreshed monthly. This avoids slow, rate-limited
        Yahoo `info` calls on every dashboard load — even after a restart.
        """
        from datetime import timedelta

        from app.database import AsyncSessionLocal
        from app.models import Stock

        symbol = symbol.upper()
        cache_key = f"stock:profile:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        async with AsyncSessionLocal() as db:
            row = await db.get(Stock, symbol)
            fresh = row and row.last_updated and (
                datetime.now(timezone.utc) - (row.last_updated if row.last_updated.tzinfo else row.last_updated.replace(tzinfo=timezone.utc))
            ) < timedelta(days=30)
            if not fresh:
                detail = await self.get_stock_detail(symbol)
                if detail and not detail.is_demo:
                    row = row or Stock(symbol=symbol, name=detail.name)
                    row.name, row.exchange, row.sector = detail.name, detail.exchange, detail.sector
                    row.industry, row.country, row.currency = detail.industry, detail.country, detail.currency
                    row.last_updated = datetime.now(timezone.utc)
                    await db.merge(row)
                    await db.commit()
                elif detail:  # simulated data: don't persist, but still answer
                    row = Stock(symbol=symbol, name=detail.name, sector=detail.sector, industry=detail.industry, currency=detail.currency)
            profile = {
                "symbol": symbol,
                "name": row.name if row else symbol,
                "sector": (row.sector if row else None) or "Other",
                "industry": row.industry if row else None,
                "currency": (row.currency if row else None) or ("INR" if symbol.endswith((".NS", ".BO")) else "USD"),
            }
        await cache_set(cache_key, profile, 86400 if row else 300)
        return profile

    async def get_profiles(self, symbols: List[str]) -> dict:
        import asyncio

        profiles = await asyncio.gather(*(self.get_profile(s) for s in symbols))
        return {p["symbol"]: p for p in profiles}

    # ── History ──────────────────────────────────────────────────────────────
    async def get_history(self, symbol: str, period: str = "1y", interval: str = "1d", indicators: bool = False) -> dict:
        symbol = symbol.upper()
        period = period if period in VALID_PERIODS else "1y"
        interval = interval if interval in VALID_INTERVALS else "1d"
        cache_key = f"stock:history:{symbol}:{period}:{interval}:{int(indicators)}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        try:
            df, is_demo = await md.ahistory(symbol, period, interval)
        except md.MarketDataError as exc:
            return {"symbol": symbol, "period": period, "interval": interval, "data": [], "error": str(exc), "is_demo": False}

        if indicators and interval in ("1d", "1wk") and not df.empty:
            # Compute overlays on a longer window so SMA-200 is defined from the first visible bar
            try:
                long_df, _ = await md.ahistory(symbol, "5y" if period not in ("5y", "10y", "max") else period, interval)
                enriched = ind.add_chart_indicators(long_df).loc[df.index.min():]
            except md.MarketDataError:
                enriched = ind.add_chart_indicators(df)
        else:
            enriched = df

        intraday = interval.endswith(("m", "h"))
        data = []
        for ts, row in enriched.iterrows():
            point = {
                "date": ts.isoformat() if intraday else str(ts.date()),
                "open": _f(row.get("Open")),
                "high": _f(row.get("High")),
                "low": _f(row.get("Low")),
                "close": _f(row.get("Close")),
                "volume": int(row["Volume"]) if pd.notna(row.get("Volume")) else None,
            }
            if indicators:
                for col in ("sma_20", "sma_50", "sma_200", "bb_upper", "bb_lower", "rsi_14", "macd", "macd_signal", "macd_hist"):
                    if col in row:
                        point[col] = _f(row[col])
            data.append(point)

        closes = [p["close"] for p in data if p["close"] is not None]
        result = {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "data": data,
            "data_points": len(data),
            "period_return_pct": _f((closes[-1] / closes[0] - 1) * 100, 2) if len(closes) > 1 and closes[0] else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_delayed": True,
            "is_demo": is_demo,
            "data_source": "simulated" if is_demo else "yahoo_finance",
        }
        await cache_set(cache_key, result, 60 if intraday else CACHE_TTL["history"])
        return result

    # ── Fundamentals ─────────────────────────────────────────────────────────
    async def get_fundamentals(self, symbol: str) -> dict:
        detail = await self.get_stock_detail(symbol)
        if not detail:
            return {"symbol": symbol.upper(), "error": "No fundamental data available"}
        return {
            "symbol": detail.symbol,
            "name": detail.name,
            "description": detail.description,
            "metrics": detail.metrics.model_dump(mode="json") if detail.metrics else None,
            "is_demo": detail.is_demo,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Technical indicators ─────────────────────────────────────────────────
    async def get_technical_indicators(self, symbol: str) -> TechnicalIndicatorsResponse:
        symbol = symbol.upper()
        cache_key = f"stock:technical:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            return TechnicalIndicatorsResponse(**cached)

        try:
            hist, is_demo = await md.ahistory(symbol, "2y", "1d")
        except md.MarketDataError as exc:
            raise ValueError(str(exc)) from exc
        if hist.empty or len(hist) < 35:
            raise ValueError("Insufficient price history for technical indicators (need 35+ trading days)")

        close, high, low = hist["Close"], hist["High"], hist["Low"]
        macd_line, macd_sig, macd_hist = ind.macd(close)
        bb_up, bb_mid, bb_low = ind.bollinger(close)
        values = {
            "close": close.iloc[-1],
            "sma_20": ind.sma(close, 20).iloc[-1],
            "sma_50": ind.sma(close, 50).iloc[-1],
            "sma_200": ind.sma(close, 200).iloc[-1] if len(close) >= 200 else None,
            "ema_12": ind.ema(close, 12).iloc[-1],
            "ema_26": ind.ema(close, 26).iloc[-1],
            "rsi_14": ind.rsi(close).iloc[-1],
            "macd": macd_line.iloc[-1],
            "macd_signal": macd_sig.iloc[-1],
            "macd_hist": macd_hist.iloc[-1],
            "bb_upper": bb_up.iloc[-1],
            "bb_middle": bb_mid.iloc[-1],
            "bb_lower": bb_low.iloc[-1],
            "atr_14": ind.atr(high, low, close).iloc[-1],
            "volatility_30d": close.pct_change().tail(30).std() * np.sqrt(252) * 100,
        }
        values = {k: _f(v) for k, v in values.items()}
        signals = self._interpret(values)
        score = sum(1 if s.signal == "bullish" else -1 if s.signal == "bearish" else 0 for s in signals)
        overall = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"

        result = TechnicalIndicatorsResponse(
            symbol=symbol,
            date=hist.index[-1].date(),
            signals=signals,
            overall_signal=overall,
            is_demo=is_demo,
            **values,
        )
        await cache_set(cache_key, result.model_dump(mode="json"), CACHE_TTL["technical"])
        return result

    @staticmethod
    def _interpret(v: dict) -> List[IndicatorSignal]:
        out: List[IndicatorSignal] = []
        close = v.get("close")
        rsi = v.get("rsi_14")
        if rsi is not None:
            if rsi < 30:
                out.append(IndicatorSignal(indicator="RSI (14)", signal="bullish", detail=f"RSI {rsi:.1f} < 30: potentially oversold"))
            elif rsi > 70:
                out.append(IndicatorSignal(indicator="RSI (14)", signal="bearish", detail=f"RSI {rsi:.1f} > 70: potentially overbought"))
            else:
                out.append(IndicatorSignal(indicator="RSI (14)", signal="neutral", detail=f"RSI {rsi:.1f} in the neutral 30–70 band"))
        if v.get("macd") is not None and v.get("macd_signal") is not None:
            bull = v["macd"] > v["macd_signal"]
            out.append(IndicatorSignal(
                indicator="MACD", signal="bullish" if bull else "bearish",
                detail=f"MACD line is {'above' if bull else 'below'} its signal line ({'positive' if bull else 'negative'} momentum)",
            ))
        if close is not None and v.get("sma_50") is not None:
            above = close > v["sma_50"]
            out.append(IndicatorSignal(
                indicator="Trend (SMA 50)", signal="bullish" if above else "bearish",
                detail=f"Price is {'above' if above else 'below'} the 50-day moving average",
            ))
        if v.get("sma_50") is not None and v.get("sma_200") is not None:
            golden = v["sma_50"] > v["sma_200"]
            out.append(IndicatorSignal(
                indicator="SMA 50 / SMA 200", signal="bullish" if golden else "bearish",
                detail="50-day SMA above 200-day SMA (golden-cross regime)" if golden else "50-day SMA below 200-day SMA (death-cross regime)",
            ))
        if close is not None and v.get("bb_upper") is not None and v.get("bb_lower") is not None:
            if close > v["bb_upper"]:
                out.append(IndicatorSignal(indicator="Bollinger Bands", signal="bearish", detail="Price above the upper band: stretched to the upside"))
            elif close < v["bb_lower"]:
                out.append(IndicatorSignal(indicator="Bollinger Bands", signal="bullish", detail="Price below the lower band: stretched to the downside"))
            else:
                out.append(IndicatorSignal(indicator="Bollinger Bands", signal="neutral", detail="Price inside the bands"))
        return out

    # ── Market overview ──────────────────────────────────────────────────────
    async def get_market_overview(self) -> MarketOverviewResponse:
        cached = await cache_get("market:overview")
        if cached:
            return MarketOverviewResponse(**cached)

        index_quotes = await md.aquotes(list(MAJOR_INDICES))
        indices = [
            {
                "symbol": sym,
                "name": name,
                "value": q["price"],
                "change": q["change"],
                "change_pct": q["change_pct"],
                "is_demo": q["is_demo"],
            }
            for sym, name in MAJOR_INDICES.items()
            if (q := index_quotes.get(sym))
        ]

        mover_quotes = await md.aquotes(MOVERS_UNIVERSE)
        movers = [
            {
                "symbol": q["symbol"],
                "price": round(q["price"], 2),
                "change": round(q["change"], 2),
                "change_pct": q["change_pct"],
                "volume": q.get("volume") or 0,
                "is_demo": q["is_demo"],
            }
            for q in mover_quotes.values()
        ]

        ranked = sorted(movers, key=lambda m: m["change_pct"], reverse=True)
        result = MarketOverviewResponse(
            indices=indices,
            top_gainers=[m for m in ranked if m["change_pct"] > 0][:5],
            top_losers=[m for m in reversed(ranked) if m["change_pct"] < 0][:5],
            most_active=sorted(movers, key=lambda m: m.get("volume", 0), reverse=True)[:5],
            market_status=us_market_status(),
            as_of=datetime.now(timezone.utc),
            is_demo=any(i["is_demo"] for i in indices) or any(m["is_demo"] for m in movers),
        )
        await cache_set("market:overview", result.model_dump(mode="json"), CACHE_TTL["overview"])
        return result

    # ── Quotes ───────────────────────────────────────────────────────────────
    async def get_quotes(self, symbols: List[str]) -> dict:
        return await md.aquotes(symbols)

    # ── Comparison ───────────────────────────────────────────────────────────
    async def compare_stocks(self, symbols: List[str], period: str = "1y") -> dict:
        symbols = [s.upper() for s in symbols]
        details = {}
        for s in symbols:
            d = await self.get_stock_detail(s)
            details[s] = d.model_dump(mode="json") if d else None

        performance: List[dict] = []
        stats: dict = {}
        try:
            closes, demo_syms = await md.acloses(symbols, period=period)
            closes = closes[[s for s in symbols if s in closes.columns]].dropna(how="any")
            if not closes.empty:
                normalized = (closes / closes.iloc[0] - 1) * 100
                step = max(1, len(normalized) // 150)  # keep the chart payload small
                sampled = normalized.iloc[::step]
                if sampled.index[-1] != normalized.index[-1]:
                    sampled = pd.concat([sampled, normalized.iloc[[-1]]])
                performance = [
                    {"date": str(ts.date()), **{s: _f(row[s], 2) for s in normalized.columns}}
                    for ts, row in sampled.iterrows()
                ]
                returns = closes.pct_change().dropna()
                for s in closes.columns:
                    r = returns[s]
                    cum = (1 + r).cumprod()
                    stats[s] = {
                        "period_return_pct": _f((closes[s].iloc[-1] / closes[s].iloc[0] - 1) * 100, 2),
                        "volatility_pct": _f(r.std() * np.sqrt(252) * 100, 2),
                        "max_drawdown_pct": _f(((cum - cum.cummax()) / cum.cummax()).min() * 100, 2),
                        "sharpe_ratio": _f((r.mean() * 252 - 0.05) / (r.std() * np.sqrt(252)), 2) if r.std() > 0 else None,
                        "is_demo": s in demo_syms,
                    }
                corr = returns.corr().round(3)
                stats["_correlation"] = {"symbols": list(corr.columns), "matrix": corr.values.tolist()}
        except md.MarketDataError:
            pass

        correlation = stats.pop("_correlation", None)
        return {
            "symbols": symbols,
            "period": period,
            "comparison": {s: {"detail": details[s], "stats": stats.get(s)} for s in symbols},
            "performance": performance,
            "correlation": correlation,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

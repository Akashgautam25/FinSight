"""
FinSight AI — Market Data Layer

Single entry point for all price / fundamentals / news data used by the services.

    live source  : Yahoo Finance via `yfinance` (free, no API key)
    fallback     : DemoDataProvider (deterministic simulation, flagged is_demo=True)

Behaviour is controlled by MARKET_DATA_MODE (auto | live | demo):
  * auto — try live first; on failure or empty data fall back to simulated data
  * live — live only; failures raise MarketDataError
  * demo — simulated only (offline demos and automated tests)

All functions here are synchronous (yfinance is blocking). Async callers must use
the `a*` wrappers, which run them in a worker thread so the event loop never blocks.

A small circuit breaker stops hammering Yahoo when the network is down: after
several consecutive failures, live calls are skipped for a cool-down period so
offline demos stay fast.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.config import settings
from app.data.providers.demo_provider import DemoDataProvider, is_known_symbol

logger = logging.getLogger("finsight.market_data")

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


class MarketDataError(Exception):
    """Raised when data is unavailable and fallback is disabled."""


# ── Tiny thread-safe TTL cache for DataFrames / dicts ─────────────────────────

class _TTLCache:
    def __init__(self, max_items: int = 512):
        self._data: Dict[tuple, Tuple[float, object]] = {}
        self._lock = threading.Lock()
        self._max = max_items

    def get(self, key: tuple):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if item[0] < time.monotonic():
                self._data.pop(key, None)
                return None
            return item[1]

    def set(self, key: tuple, value, ttl: float) -> None:
        with self._lock:
            if len(self._data) >= self._max:
                self._data.clear()
            self._data[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = _TTLCache()


class _CircuitBreaker:
    def __init__(self, threshold: int = 4, cooldown: float = 90.0):
        self.threshold, self.cooldown = threshold, cooldown
        self._failures = 0
        self._open_until = 0.0
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self._open_until

    def success(self) -> None:
        with self._lock:
            self._failures = 0

    def trip(self) -> None:
        with self._lock:
            self._open_until = time.monotonic() + self.cooldown
            self._failures = 0
        logger.warning("Live market data unreachable — using simulated data for %ss", self.cooldown)

    def failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold:
                self._open_until = time.monotonic() + self.cooldown
                self._failures = 0
                logger.warning("Live market data unreachable — using simulated data for %ss", self.cooldown)


_breaker = _CircuitBreaker()


_probe = {"at": 0.0, "ok": True}
_probe_lock = threading.Lock()


def _live_reachable() -> bool:
    """Is Yahoo Finance answering at all? (cached 2 min)

    yfinance returns an empty frame both for unknown tickers and when the network
    is down, so an empty answer is ambiguous. Probing a liquid ETF resolves it.
    """
    with _probe_lock:
        if time.monotonic() - _probe["at"] < 120:
            return _probe["ok"]
    ok = False
    try:
        import yfinance as yf

        ok = not yf.Ticker("SPY").history(period="5d", interval="1d", timeout=10).empty
    except Exception:
        ok = False
    with _probe_lock:
        _probe.update(at=time.monotonic(), ok=ok)
    if ok:
        _breaker.success()
    else:
        _breaker.trip()
    return ok


def _mode() -> str:
    return (settings.market_data_mode or "auto").lower()


def _live_allowed() -> bool:
    return _mode() != "demo" and not (_mode() == "auto" and _breaker.is_open)


def _fallback_allowed() -> bool:
    return _mode() != "live"


def data_status() -> dict:
    return {
        "mode": _mode(),
        "live_available": not _breaker.is_open,
        "source": "demo" if _mode() == "demo" else "yahoo_finance",
    }


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV)
    df = df[[c for c in OHLCV if c in df.columns]].copy()
    df = df.dropna(subset=["Close"])
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx
    return df.sort_index()


# ── History ──────────────────────────────────────────────────────────────────

def history(symbol: str, period: str = "1y", interval: str = "1d") -> Tuple[pd.DataFrame, bool]:
    """Return (OHLCV DataFrame indexed by naive datetime, is_demo)."""
    symbol = symbol.upper()
    key = ("hist", symbol, period, interval)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    if _live_allowed():
        try:
            import yfinance as yf

            df = _clean_ohlcv(yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True, timeout=15))
            if not df.empty:
                _breaker.success()
                result = (df, False)
                _cache.set(key, result, 60 if interval.endswith(("m", "h")) else 300)
                return result
            # Empty answer for an unknown ticker → it doesn't exist. For a well-known
            # ticker it signals an outage: probe Yahoo so the circuit breaker can trip.
            if not is_known_symbol(symbol):
                raise MarketDataError(f"No price history available for {symbol}")
            _live_reachable()
        except MarketDataError:
            raise
        except Exception as exc:
            logger.info("Live history failed for %s: %s", symbol, exc)
            _breaker.failure()

    if not _fallback_allowed() or not is_known_symbol(symbol):
        # Simulated data is only offered for the curated demo universe — never invented companies.
        raise MarketDataError(f"No price history available for {symbol}")

    result = (DemoDataProvider.history(symbol, period, interval), True)
    _cache.set(key, result, 300)
    return result


def bars(symbols: List[str], period: str = "1y") -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """Daily close and volume frames for several symbols in ONE request.

    Returns (close_df, volume_df, demo_symbols); columns are the symbols.
    """
    symbols = list(dict.fromkeys(s.upper() for s in symbols))
    key = ("bars", tuple(sorted(symbols)), period)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    close_df, vol_df = pd.DataFrame(), pd.DataFrame()
    if _live_allowed():
        try:
            import yfinance as yf

            raw = yf.download(symbols, period=period, interval="1d", progress=False, auto_adjust=True, threads=True, timeout=20)
            if raw is not None and not raw.empty:
                def _field(name: str) -> pd.DataFrame:
                    f = raw[name]
                    if isinstance(f, pd.Series):
                        f = f.to_frame(symbols[0])
                    idx = pd.to_datetime(f.index)
                    f.index = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
                    return f
                close_df = _field("Close").dropna(axis=1, how="all")
                vol_df = _field("Volume")[close_df.columns]
                _breaker.success()
        except Exception as exc:
            logger.info("Live download failed for %s: %s", symbols, exc)
            _breaker.failure()

    demo_symbols: List[str] = []
    missing = [s for s in symbols if s not in close_df.columns]
    if missing:
        if not _fallback_allowed():
            raise MarketDataError(f"No price data for: {', '.join(missing)}")
        for s in missing:
            if not is_known_symbol(s):
                continue  # unknown ticker (or no simulated profile available) → drop it
            demo = DemoDataProvider.history(s, period, "1d")
            close_df = demo["Close"].to_frame(s) if close_df.empty else close_df.join(demo["Close"].rename(s), how="outer")
            vol_df = demo["Volume"].to_frame(s) if vol_df.empty else vol_df.join(demo["Volume"].rename(s), how="outer")
            demo_symbols.append(s)

    # No forward-fill here: markets with different holiday calendars (US vs India)
    # must keep their own last/previous close for correct daily change figures.
    close_df = close_df.sort_index().dropna(how="all")
    vol_df = vol_df.reindex(close_df.index)
    result = (close_df, vol_df, demo_symbols)
    _cache.set(key, result, 300 if period in ("1d", "5d") else 900)
    return result


def closes(symbols: List[str], period: str = "1y") -> Tuple[pd.DataFrame, List[str]]:
    """Daily close prices for several symbols (columns = symbols). Returns (df, demo_symbols)."""
    close_df, _, demo_symbols = bars(symbols, period)
    # Align calendars for return calculations (holiday gaps carry the last price).
    return close_df.ffill(limit=5).dropna(how="all"), demo_symbols


# ── Quote + fundamentals ─────────────────────────────────────────────────────

def info(symbol: str) -> Tuple[dict, bool]:
    """Normalized Yahoo-style `info` dict with an up-to-date price. Returns (info, is_demo)."""
    symbol = symbol.upper()
    key = ("info", symbol)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    if _live_allowed():
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            data: dict = {}
            try:
                data = dict(ticker.info or {})
            except Exception as exc:  # .info is the most rate-limited endpoint
                logger.info("Live info failed for %s: %s", symbol, exc)
            hist, hist_is_demo = history(symbol, "5d", "1d")
            if not hist.empty and not hist_is_demo:
                last, prev = hist.iloc[-1], (hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1])
                data.setdefault("symbol", symbol)
                data["currentPrice"] = float(last["Close"])
                data["previousClose"] = float(prev["Close"])
                data["dayHigh"] = float(last["High"])
                data["dayLow"] = float(last["Low"])
                data["volume"] = int(last["Volume"]) if pd.notna(last["Volume"]) else None
                data.setdefault("currency", "INR" if symbol.endswith((".NS", ".BO")) else "USD")
                _breaker.success()
                result = (data, False)
                _cache.set(key, result, 300)
                return result
        except MarketDataError:
            pass
        except Exception as exc:
            logger.info("Live quote failed for %s: %s", symbol, exc)
            _breaker.failure()

    if not _fallback_allowed() or not is_known_symbol(symbol):
        raise MarketDataError(f"No quote available for {symbol}")

    result = (DemoDataProvider.info(symbol), True)
    _cache.set(key, result, 300)
    return result


def quotes(symbols: List[str]) -> Dict[str, dict]:
    """Fast batch quotes (price, previous close, change %, volume) from one download call."""
    if not symbols:
        return {}
    close_df, vol_df, demo_symbols = bars(symbols, period="5d")
    out: Dict[str, dict] = {}
    for s in dict.fromkeys(x.upper() for x in symbols):
        if s not in close_df.columns:
            continue
        series = close_df[s].dropna()
        if series.empty:
            continue
        last = float(series.iloc[-1])
        prev = float(series.iloc[-2]) if len(series) > 1 else last
        vol = vol_df[s].dropna() if s in vol_df.columns else pd.Series(dtype=float)
        out[s] = {
            "symbol": s,
            "price": round(last, 4),
            "previous_close": round(prev, 4),
            "change": round(last - prev, 4),
            "change_pct": round((last - prev) / prev * 100, 2) if prev else 0.0,
            "volume": int(vol.iloc[-1]) if not vol.empty else None,
            "is_demo": s in demo_symbols,
        }
    return out


# ── Search & news ────────────────────────────────────────────────────────────

def search(query: str, limit: int = 10) -> List[dict]:
    results: List[dict] = []
    if _live_allowed():
        try:
            import yfinance as yf

            for q in yf.Search(query, max_results=max(limit, 10), news_count=0).quotes:
                if q.get("quoteType") not in ("EQUITY", "ETF", "INDEX"):
                    continue
                results.append({
                    "symbol": q.get("symbol"),
                    "name": q.get("longname") or q.get("shortname") or q.get("symbol"),
                    "exchange": q.get("exchDisp") or q.get("exchange"),
                    "sector": q.get("sectorDisp") or q.get("sector"),
                    "industry": q.get("industryDisp") or q.get("industry"),
                    "country": None,
                    "currency": "INR" if str(q.get("symbol", "")).endswith((".NS", ".BO")) else "USD",
                })
            _breaker.success()
        except Exception as exc:
            logger.info("Live search failed for %s: %s", query, exc)
            _breaker.failure()

    if not results and _fallback_allowed():
        results = DemoDataProvider.search(query, limit)
    return results[:limit]


def _normalize_yahoo_news(item: dict) -> Optional[dict]:
    content = item.get("content") if isinstance(item.get("content"), dict) else None
    if content:  # 2025+ format
        url = (content.get("canonicalUrl") or {}).get("url") or (content.get("clickThroughUrl") or {}).get("url")
        title = content.get("title")
        if not title or not url:
            return None
        return {
            "id": item.get("id") or content.get("id") or url,
            "title": title,
            "summary": content.get("summary") or content.get("description"),
            "url": url,
            "source": (content.get("provider") or {}).get("displayName") or "Yahoo Finance",
            "author": None,
            "published_at": content.get("pubDate") or content.get("displayTime"),
        }
    if item.get("title") and item.get("link"):  # legacy format
        ts = item.get("providerPublishTime")
        return {
            "id": item.get("uuid") or item["link"],
            "title": item["title"],
            "summary": None,
            "url": item["link"],
            "source": item.get("publisher"),
            "author": None,
            "published_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
        }
    return None


def news(symbol: str, limit: int = 10) -> Tuple[List[dict], bool]:
    """Headlines for a ticker (or index such as ^GSPC). Returns (articles, is_demo)."""
    symbol = symbol.upper()
    key = ("news", symbol, limit)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    if _live_allowed():
        try:
            import yfinance as yf

            raw = yf.Ticker(symbol).get_news(count=limit) if hasattr(yf.Ticker, "get_news") else yf.Ticker(symbol).news
            articles = [a for a in (_normalize_yahoo_news(i) for i in (raw or [])) if a]
            _breaker.success()
            if articles:
                result = (articles[:limit], False)
                _cache.set(key, result, 900)
                return result
        except Exception as exc:
            logger.info("Live news failed for %s: %s", symbol, exc)
            _breaker.failure()

    if not _fallback_allowed():
        return [], False
    result = (DemoDataProvider.news(None if symbol.startswith("^") else symbol, limit), True)
    _cache.set(key, result, 900)
    return result


def clear_cache() -> None:
    _cache.clear()


# ── Async wrappers (never block the event loop) ──────────────────────────────

async def ahistory(symbol: str, period: str = "1y", interval: str = "1d"):
    return await asyncio.to_thread(history, symbol, period, interval)


async def acloses(symbols: List[str], period: str = "1y"):
    return await asyncio.to_thread(closes, symbols, period)


async def ainfo(symbol: str):
    return await asyncio.to_thread(info, symbol)


async def abars(symbols: List[str], period: str = "1y"):
    return await asyncio.to_thread(bars, symbols, period)


async def aquotes(symbols: List[str]):
    return await asyncio.to_thread(quotes, symbols)


async def asearch(query: str, limit: int = 10):
    return await asyncio.to_thread(search, query, limit)


async def anews(symbol: str, limit: int = 10):
    return await asyncio.to_thread(news, symbol, limit)

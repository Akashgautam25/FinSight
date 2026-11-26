"""
FinSight AI — News & Sentiment Service

Sources (first that returns data wins):
  1. Finnhub        (optional, FINNHUB_API_KEY)
  2. NewsAPI        (optional, NEWS_API_KEY — market headlines)
  3. Yahoo Finance  (free, no key — default)
  4. Simulated feed (offline fallback, flagged is_demo)

Every article is scored by the SentimentService (FinBERT or lexicon model).
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from app.config import settings
from app.data import market_data as md
from app.services.sentiment_service import SentimentService, model_status
from app.utils.cache import cache_get, cache_set

# Category → tickers whose Yahoo news feed represents that sector
CATEGORY_FEEDS = {
    None: ["^GSPC", "^IXIC", "AAPL", "NVDA"],
    "general": ["^GSPC", "^IXIC", "AAPL", "NVDA"],
    "technology": ["XLK", "MSFT", "NVDA"],
    "finance": ["XLF", "JPM", "GS"],
    "healthcare": ["XLV", "JNJ", "PFE"],
    "energy": ["XLE", "XOM", "CVX"],
    "consumer": ["XLY", "AMZN", "WMT"],
    "india": ["^NSEI", "RELIANCE.NS", "TCS.NS"],
}


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _dedupe_sort(articles: List[dict]) -> List[dict]:
    seen, out = set(), []
    for a in articles:
        key = (a.get("title") or "").strip().lower()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(a)
    out.sort(key=lambda a: _parse_dt(a.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out


class NewsService:
    def __init__(self):
        self.sentiment = SentimentService()

    async def _score(self, articles: List[dict]) -> List[dict]:
        if not articles:
            return articles
        texts = [f"{a.get('title', '')}. {a.get('summary') or ''}".strip() for a in articles]
        scores = await self.sentiment.analyze_batch(texts)
        for a, s in zip(articles, scores):
            a.update(s)
        return articles

    # ── Market / sector news ─────────────────────────────────────────────────
    async def get_market_news(self, limit: int = 20, category: Optional[str] = None) -> dict:
        category = (category or "").lower() or None
        if category == "all":
            category = None
        cache_key = f"news:market:{limit}:{category}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        articles: List[dict] = []
        source = "yahoo_finance"
        is_demo = False

        if settings.news_api_key and category in (None, "general"):
            articles = await self._fetch_newsapi_headlines(limit)
            source = "newsapi" if articles else source
        if not articles and settings.finnhub_api_key and category in (None, "general"):
            articles = await self._fetch_finnhub_market()
            source = "finnhub" if articles else source

        if not articles:
            feeds = CATEGORY_FEEDS.get(category, [category.upper()] if category else CATEGORY_FEEDS[None])
            per_feed = max(5, limit // len(feeds) + 3)
            results = await asyncio.gather(*(md.anews(sym, per_feed) for sym in feeds), return_exceptions=True)
            demo_flags = []
            for res in results:
                if isinstance(res, Exception):
                    continue
                items, demo = res
                articles.extend(items)
                demo_flags.append(demo)
            is_demo = bool(demo_flags) and all(demo_flags)
            source = "simulated" if is_demo else "yahoo_finance"

        articles = await self._score(_dedupe_sort(articles)[:limit])
        result = {
            "articles": articles,
            "total": len(articles),
            "category": category or "all",
            "source": source,
            "sentiment_model": model_status()["active_model"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": is_demo,
        }
        await cache_set(cache_key, result, ttl=600)
        return result

    async def get_sector_news(self, sector: str, limit: int = 20) -> dict:
        return await self.get_market_news(limit=limit, category=sector)

    # ── Company news ─────────────────────────────────────────────────────────
    async def get_stock_news(self, symbol: str, limit: int = 20, days: int = 7) -> dict:
        symbol = symbol.upper()
        cache_key = f"news:stock:{symbol}:{limit}:{days}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        articles: List[dict] = []
        source, is_demo = "yahoo_finance", False
        if settings.finnhub_api_key:
            articles = await self._fetch_finnhub_company(symbol, days)
            source = "finnhub" if articles else source
        if not articles:
            articles, is_demo = await md.anews(symbol, max(limit, 10))
            source = "simulated" if is_demo else "yahoo_finance"

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [a for a in articles if (_parse_dt(a.get("published_at")) or datetime.now(timezone.utc)) >= cutoff]
        # Yahoo returns the latest ~10 stories; keep them if the window filter removes everything
        articles = recent or articles
        articles = await self._score(_dedupe_sort(articles)[:limit])

        result = {
            "symbol": symbol,
            "articles": articles,
            "total": len(articles),
            "source": source,
            "sentiment_model": model_status()["active_model"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": is_demo,
        }
        await cache_set(cache_key, result, ttl=600)
        return result

    async def get_sentiment_summary(self, symbol: str, days: int = 30) -> dict:
        news = await self.get_stock_news(symbol, limit=50, days=days)
        articles = news.get("articles", [])
        now = datetime.now(timezone.utc).isoformat()

        if not articles:
            return {
                "symbol": symbol.upper(), "overall_sentiment": "neutral", "positive_pct": 0.0,
                "negative_pct": 0.0, "neutral_pct": 100.0, "avg_compound_score": 0.0, "news_count": 0,
                "period_days": days, "as_of": now, "sentiment_model": news.get("sentiment_model"),
                "most_positive": None, "most_negative": None, "is_demo": news.get("is_demo", False),
            }

        n = len(articles)
        labels = [a.get("sentiment", "neutral") for a in articles]
        compounds = [float(a.get("compound_score") or 0) for a in articles]
        avg = sum(compounds) / n
        best = max(articles, key=lambda a: a.get("compound_score") or 0)
        worst = min(articles, key=lambda a: a.get("compound_score") or 0)

        return {
            "symbol": symbol.upper(),
            "overall_sentiment": "positive" if avg > 0.1 else "negative" if avg < -0.1 else "neutral",
            "positive_pct": round(labels.count("positive") / n * 100, 1),
            "negative_pct": round(labels.count("negative") / n * 100, 1),
            "neutral_pct": round(labels.count("neutral") / n * 100, 1),
            "avg_compound_score": round(avg, 4),
            "news_count": n,
            "period_days": days,
            "as_of": now,
            "sentiment_model": news.get("sentiment_model"),
            "most_positive": {"title": best["title"], "url": best.get("url"), "score": best.get("compound_score")} if (best.get("compound_score") or 0) > 0 else None,
            "most_negative": {"title": worst["title"], "url": worst.get("url"), "score": worst.get("compound_score")} if (worst.get("compound_score") or 0) < 0 else None,
            "is_demo": news.get("is_demo", False),
        }

    # ── Optional keyed providers ─────────────────────────────────────────────
    async def _fetch_newsapi_headlines(self, limit: int) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params={"category": "business", "language": "en", "pageSize": limit},
                    headers={"X-Api-Key": settings.news_api_key},
                )
            if resp.status_code != 200:
                return []
            out = []
            for a in resp.json().get("articles", []):
                if not a.get("title") or a["title"] == "[Removed]" or not a.get("url"):
                    continue
                out.append({
                    "id": hashlib.md5(a["url"].encode()).hexdigest(),
                    "title": a["title"], "summary": a.get("description"), "url": a["url"],
                    "source": (a.get("source") or {}).get("name"), "author": a.get("author"),
                    "published_at": a.get("publishedAt"),
                })
            return out
        except Exception:
            return []

    async def _fetch_finnhub_market(self) -> List[dict]:
        return await self._finnhub("https://finnhub.io/api/v1/news", {"category": "general"})

    async def _fetch_finnhub_company(self, symbol: str, days: int) -> List[dict]:
        to_date = datetime.now(timezone.utc)
        return await self._finnhub(
            "https://finnhub.io/api/v1/company-news",
            {"symbol": symbol, "from": (to_date - timedelta(days=days)).strftime("%Y-%m-%d"), "to": to_date.strftime("%Y-%m-%d")},
        )

    async def _finnhub(self, url: str, params: dict) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params={**params, "token": settings.finnhub_api_key})
            if resp.status_code != 200:
                return []
            out = []
            for a in resp.json()[:50]:
                if not a.get("headline") or not a.get("url"):
                    continue
                out.append({
                    "id": hashlib.md5(str(a.get("id", a["url"])).encode()).hexdigest(),
                    "title": a["headline"], "summary": a.get("summary"), "url": a["url"],
                    "source": a.get("source"), "author": None,
                    "published_at": datetime.fromtimestamp(a["datetime"], tz=timezone.utc).isoformat() if a.get("datetime") else None,
                })
            return out
        except Exception:
            return []

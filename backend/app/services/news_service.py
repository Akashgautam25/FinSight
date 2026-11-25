"""
FinSight AI — News & Sentiment Service
Fetches news and runs FinBERT sentiment analysis.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import httpx

from app.config import settings
from app.utils.cache import cache_get, cache_set


class NewsService:
    async def get_market_news(self, limit: int = 20, category: Optional[str] = None) -> dict:
        cache_key = f"news:market:{limit}:{category}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        articles = []

        # Try NewsAPI
        if settings.news_api_key:
            async with httpx.AsyncClient(timeout=10) as client:
                try:
                    resp = await client.get(
                        "https://newsapi.org/v2/top-headlines",
                        params={
                            "category": "business",
                            "language": "en",
                            "pageSize": limit,
                            "apiKey": settings.news_api_key,
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        articles = self._format_newsapi(data.get("articles", []))
                except Exception:
                    pass

        # Fallback to Finnhub
        if not articles and settings.finnhub_api_key:
            articles = await self._fetch_finnhub_news(category="general")

        result = {
            "articles": articles[:limit],
            "total": len(articles),
            "source": "newsapi" if settings.news_api_key else "finnhub",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": not articles,
        }

        await cache_set(cache_key, result, ttl=600)
        return result

    async def get_stock_news(self, symbol: str, limit: int = 20, days: int = 7) -> dict:
        cache_key = f"news:stock:{symbol}:{limit}:{days}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        articles = []

        if settings.finnhub_api_key:
            to_date = datetime.now(timezone.utc)
            from_date = to_date - timedelta(days=days)
            async with httpx.AsyncClient(timeout=10) as client:
                try:
                    resp = await client.get(
                        "https://finnhub.io/api/v1/company-news",
                        params={
                            "symbol": symbol,
                            "from": from_date.strftime("%Y-%m-%d"),
                            "to": to_date.strftime("%Y-%m-%d"),
                            "token": settings.finnhub_api_key,
                        }
                    )
                    if resp.status_code == 200:
                        articles = self._format_finnhub(resp.json()[:limit])
                except Exception:
                    pass

        # Fallback: NewsAPI with symbol query
        if not articles and settings.news_api_key:
            async with httpx.AsyncClient(timeout=10) as client:
                try:
                    resp = await client.get(
                        "https://newsapi.org/v2/everything",
                        params={
                            "q": symbol,
                            "language": "en",
                            "sortBy": "publishedAt",
                            "pageSize": limit,
                            "apiKey": settings.news_api_key,
                        }
                    )
                    if resp.status_code == 200:
                        articles = self._format_newsapi(resp.json().get("articles", []))
                except Exception:
                    pass

        # Analyze sentiment if articles available
        if articles:
            articles = await self._add_sentiment(articles)

        result = {
            "symbol": symbol,
            "articles": articles,
            "total": len(articles),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        await cache_set(cache_key, result, ttl=600)
        return result

    async def get_sentiment_summary(self, symbol: str, days: int = 30) -> dict:
        news_data = await self.get_stock_news(symbol, limit=50, days=days)
        articles = news_data.get("articles", [])

        if not articles:
            return {
                "symbol": symbol,
                "overall_sentiment": "neutral",
                "positive_pct": 0,
                "negative_pct": 0,
                "neutral_pct": 100,
                "avg_compound_score": 0,
                "news_count": 0,
                "period_days": days,
                "as_of": datetime.now(timezone.utc).isoformat(),
            }

        sentiments = [a.get("sentiment", "neutral") for a in articles]
        pos = sentiments.count("positive") / len(sentiments) * 100
        neg = sentiments.count("negative") / len(sentiments) * 100
        neu = sentiments.count("neutral") / len(sentiments) * 100
        compound_scores = [a.get("compound_score", 0) or 0 for a in articles]
        avg_compound = sum(compound_scores) / len(compound_scores)

        overall = "positive" if avg_compound > 0.05 else "negative" if avg_compound < -0.05 else "neutral"

        return {
            "symbol": symbol,
            "overall_sentiment": overall,
            "positive_pct": round(pos, 1),
            "negative_pct": round(neg, 1),
            "neutral_pct": round(neu, 1),
            "avg_compound_score": round(avg_compound, 4),
            "news_count": len(articles),
            "period_days": days,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    async def get_sector_news(self, sector: str, limit: int = 20) -> dict:
        return await self.get_market_news(limit=limit, category=sector)

    async def _add_sentiment(self, articles: list) -> list:
        """Run FinBERT sentiment analysis on article titles+summaries."""
        try:
            from app.services.sentiment_service import SentimentService
            sentiment_service = SentimentService()
            for article in articles:
                text = f"{article.get('title', '')} {article.get('summary', '')}".strip()
                if text:
                    sentiment = await sentiment_service.analyze(text)
                    article.update(sentiment)
        except Exception:
            pass
        return articles

    async def _fetch_finnhub_news(self, category: str = "general") -> list:
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(
                    "https://finnhub.io/api/v1/news",
                    params={"category": category, "token": settings.finnhub_api_key}
                )
                if resp.status_code == 200:
                    return self._format_finnhub(resp.json())
            except Exception:
                pass
        return []

    def _format_newsapi(self, articles: list) -> list:
        result = []
        for a in articles:
            if not a.get("title") or a["title"] == "[Removed]":
                continue
            result.append({
                "id": hashlib.md5(a.get("url", "").encode()).hexdigest(),
                "title": a.get("title"),
                "summary": a.get("description"),
                "url": a.get("url"),
                "source": a.get("source", {}).get("name"),
                "author": a.get("author"),
                "published_at": a.get("publishedAt"),
                "sentiment": "neutral",
                "compound_score": 0,
            })
        return result

    def _format_finnhub(self, articles: list) -> list:
        result = []
        for a in articles:
            if not a.get("headline"):
                continue
            result.append({
                "id": hashlib.md5(str(a.get("id", a.get("url", ""))).encode()).hexdigest(),
                "title": a.get("headline"),
                "summary": a.get("summary"),
                "url": a.get("url"),
                "source": a.get("source"),
                "author": None,
                "published_at": datetime.fromtimestamp(a["datetime"], tz=timezone.utc).isoformat() if a.get("datetime") else None,
                "sentiment": "neutral",
                "compound_score": 0,
            })
        return result

"""
FinSight AI — FinBERT Sentiment Analysis Service
Uses ProsusAI/finbert for financial-domain sentiment classification.
"""

from typing import Dict
from functools import lru_cache

from app.utils.cache import cache_get, cache_set


@lru_cache(maxsize=1)
def _load_finbert():
    """Load FinBERT once and cache in memory."""
    from transformers import pipeline
    return pipeline(
        "text-classification",
        model="ProsusAI/finbert",
        return_all_scores=True,
        truncation=True,
        max_length=512,
    )


class SentimentService:
    async def analyze(self, text: str) -> Dict:
        """
        Analyze financial text sentiment using FinBERT.
        Returns sentiment label and scores (positive, negative, neutral).
        """
        import hashlib
        cache_key = f"sentiment:{hashlib.md5(text[:200].encode()).hexdigest()}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        try:
            pipe = _load_finbert()
            results = pipe(text[:512])[0]

            scores = {r["label"].lower(): r["score"] for r in results}
            positive = scores.get("positive", 0)
            negative = scores.get("negative", 0)
            neutral = scores.get("neutral", 0)

            # Compound score: positive - negative (range -1 to 1)
            compound = positive - negative

            sentiment = max(scores, key=scores.get)

            result = {
                "sentiment": sentiment,
                "positive_score": round(positive, 4),
                "negative_score": round(negative, 4),
                "neutral_score": round(neutral, 4),
                "compound_score": round(compound, 4),
                "model_used": "ProsusAI/finbert",
            }

            await cache_set(cache_key, result, ttl=86400)
            return result

        except Exception as e:
            # Fallback: neutral if model unavailable
            return {
                "sentiment": "neutral",
                "positive_score": 0.0,
                "negative_score": 0.0,
                "neutral_score": 1.0,
                "compound_score": 0.0,
                "model_used": "fallback",
            }

"""
FinSight AI — Financial Sentiment Analysis

Two interchangeable models behind one interface:

1. FinBERT (ProsusAI/finbert) — transformer fine-tuned on financial news.
   Used automatically when the optional `transformers` package is installed
   (included in requirements.txt). It is loaded in a background thread at startup
   so the API never blocks while the ~440 MB model downloads.

2. Financial lexicon model — rule-based scorer built on a Loughran-McDonald-style
   word list (finance-specific polarity: "liability", "volatile" are negative;
   "beat", "upgrade" are positive) with phrase rules, negation handling and
   intensity weighting. Zero dependencies, instant, always available.

Both return: sentiment label, positive/negative/neutral probabilities and a
compound score in [-1, 1] (positive − negative).
"""

import asyncio
import hashlib
import logging
import re
import threading
from typing import Dict, List, Optional

from app.config import settings
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger("finsight.sentiment")

# ── Lexicon ──────────────────────────────────────────────────────────────────

POSITIVE_WORDS = {
    "beat", "beats", "beating", "exceed", "exceeds", "exceeded", "surpass", "surpassed", "outperform",
    "outperforms", "outperformed", "upgrade", "upgrades", "upgraded", "raise", "raises", "raised",
    "gain", "gains", "gained", "surge", "surges", "surged", "soar", "soars", "soared", "jump", "jumps",
    "jumped", "rally", "rallies", "rallied", "rebound", "rebounds", "rebounded", "record", "growth",
    "grow", "grows", "grew", "profit", "profits", "profitable", "profitability", "strong", "stronger",
    "strength", "robust", "boost", "boosts", "boosted", "expand", "expands", "expanded", "expansion",
    "bullish", "optimistic", "optimism", "upbeat", "positive", "improve", "improves", "improved",
    "improvement", "accelerate", "accelerates", "accelerated", "momentum", "win", "wins", "won",
    "breakthrough", "innovative", "innovation", "launch", "launches", "launched", "approval", "approved",
    "buyback", "dividend", "dividends", "upside", "higher", "highs", "climb", "climbs", "climbed",
    "advance", "advances", "advanced", "recover", "recovers", "recovered", "recovery", "efficient",
    "lucrative", "success", "successful", "milestone", "partnership", "demand", "tops", "topped",
}

NEGATIVE_WORDS = {
    "miss", "misses", "missed", "downgrade", "downgrades", "downgraded", "cut", "cuts", "cutting",
    "loss", "losses", "lose", "loses", "lost", "decline", "declines", "declined", "drop", "drops",
    "dropped", "fall", "falls", "fell", "plunge", "plunges", "plunged", "slump", "slumps", "slumped",
    "tumble", "tumbles", "tumbled", "sink", "sinks", "sank", "crash", "crashes", "crashed", "slide",
    "slides", "slid", "weak", "weaker", "weakness", "bearish", "pessimistic", "concern", "concerns",
    "worried", "worry", "worries", "fear", "fears", "risk", "risks", "risky", "volatile", "volatility",
    "uncertain", "uncertainty", "lawsuit", "lawsuits", "sue", "sued", "probe", "investigation",
    "investigations", "fine", "fined", "penalty", "fraud", "scandal", "recall", "recalls", "layoff",
    "layoffs", "bankruptcy", "bankrupt", "default", "defaults", "debt", "liability", "liabilities",
    "warning", "warns", "warned", "lower", "lows", "slowdown", "slow", "slows", "slowing", "recession",
    "inflation", "headwind", "headwinds", "disappoint", "disappoints", "disappointed", "disappointing",
    "negative", "underperform", "underperforms", "underperformed", "shortfall", "delay", "delays",
    "delayed", "halt", "halts", "halted", "suspend", "suspended", "tariff", "tariffs", "sanction",
    "sanctions", "selloff", "sell-off", "glut", "deficit", "impairment", "writedown", "restructuring",
    "downturn", "struggle", "struggles", "struggling", "threat", "threatens", "pressure", "pressures",
    "slip", "slips", "slipped", "shrink", "shrinks", "shrank", "breach", "hack", "outage",
}

# Multi-word expressions are scored before single words (weights > 1 = strong signals)
PHRASES = {
    "beats expectations": 2.0, "beat expectations": 2.0, "tops estimates": 2.0, "above estimates": 1.5,
    "raises guidance": 2.0, "raised guidance": 2.0, "price target raised": 1.5, "raises price target": 1.5,
    "record high": 1.5, "all-time high": 1.5, "share buyback": 1.0, "dividend increase": 1.5,
    "misses expectations": -2.0, "missed expectations": -2.0, "below estimates": -1.5, "misses estimates": -2.0,
    "cuts guidance": -2.0, "lowers guidance": -2.0, "price target cut": -1.5, "cuts price target": -1.5,
    "profit warning": -2.0, "52-week low": -1.5, "going concern": -2.0, "class action": -1.5,
}

NEGATIONS = {"not", "no", "never", "without", "neither", "nor", "hardly", "barely", "fails", "failed", "isn't", "wasn't", "didn't", "doesn't", "won't", "can't"}
INTENSIFIERS = {"sharply": 1.5, "significantly": 1.4, "strongly": 1.4, "massive": 1.5, "huge": 1.4, "record": 1.3, "slightly": 0.6, "modestly": 0.7}

_TOKEN_RE = re.compile(r"[a-z][a-z'\-]*")


def lexicon_sentiment(text: str) -> Dict:
    """Score financial text with the lexicon model."""
    lowered = text.lower()
    score_pos, score_neg = 0.0, 0.0

    for phrase, weight in PHRASES.items():
        if phrase in lowered:
            if weight > 0:
                score_pos += weight
            else:
                score_neg += -weight
            lowered = lowered.replace(phrase, " ")

    tokens = _TOKEN_RE.findall(lowered)
    for i, tok in enumerate(tokens):
        polarity = 1 if tok in POSITIVE_WORDS else -1 if tok in NEGATIVE_WORDS else 0
        if not polarity:
            continue
        window = tokens[max(0, i - 3):i]
        weight = 1.0
        for w in window:
            weight *= INTENSIFIERS.get(w, 1.0)
        if any(w in NEGATIONS for w in window):
            polarity = -polarity
            weight *= 0.8
        if polarity > 0:
            score_pos += weight
        else:
            score_neg += weight

    total = score_pos + score_neg
    if total == 0:
        pos, neg, neu = 0.05, 0.05, 0.90
    else:
        # Evidence-weighted probabilities: more polar words → less neutral mass
        neu = 1.0 / (1.0 + total)
        pos = (1 - neu) * score_pos / total
        neg = (1 - neu) * score_neg / total

    compound = pos - neg
    label = "positive" if compound > 0.15 else "negative" if compound < -0.15 else "neutral"
    return {
        "sentiment": label,
        "positive_score": round(pos, 4),
        "negative_score": round(neg, 4),
        "neutral_score": round(neu, 4),
        "compound_score": round(compound, 4),
        "model_used": "finsight-lexicon-v1",
    }


# ── FinBERT (optional) ───────────────────────────────────────────────────────

_finbert = None
_finbert_state = "disabled"  # disabled | loading | ready | unavailable
_finbert_lock = threading.Lock()


def _load_finbert() -> None:
    global _finbert, _finbert_state
    try:
        from app.ml.models import configure_torch  # loads XGBoost before torch (OpenMP conflict on macOS)
        from transformers import pipeline  # optional dependency

        configure_torch()  # single-threaded torch avoids the torch/XGBoost OpenMP deadlock

        logger.info("Loading FinBERT (ProsusAI/finbert) in background…")
        pipe = pipeline("text-classification", model="ProsusAI/finbert", top_k=None, truncation=True, max_length=512)
        pipe(["warm-up sentence"])  # first call compiles kernels
        with _finbert_lock:
            _finbert, _finbert_state = pipe, "ready"
        logger.info("FinBERT ready — sentiment now uses the transformer model")
    except ImportError:
        _finbert_state = "unavailable"
        logger.info("transformers not installed — using the lexicon sentiment model")
    except Exception as exc:  # download failure, no disk space, …
        _finbert_state = "unavailable"
        logger.warning("FinBERT failed to load (%s) — using the lexicon sentiment model", exc)


def start_finbert_loading() -> None:
    """Kick off background loading (called once at application startup)."""
    global _finbert_state
    if settings.sentiment_backend.lower() == "lexicon" or _finbert_state != "disabled":
        return
    try:
        import importlib.util

        if importlib.util.find_spec("transformers") is None:
            _finbert_state = "unavailable"
            return
    except Exception:
        _finbert_state = "unavailable"
        return
    _finbert_state = "loading"
    threading.Thread(target=_load_finbert, name="finbert-loader", daemon=True).start()


def model_status() -> Dict:
    return {
        "active_model": "ProsusAI/finbert" if _finbert_state == "ready" else "finsight-lexicon-v1",
        "finbert_state": _finbert_state,
    }


def _finbert_batch(texts: List[str]) -> List[Dict]:
    outputs = _finbert([t[:2000] for t in texts], batch_size=16)
    results = []
    for scores in outputs:
        s = {r["label"].lower(): float(r["score"]) for r in scores}
        pos, neg, neu = s.get("positive", 0.0), s.get("negative", 0.0), s.get("neutral", 0.0)
        results.append({
            "sentiment": max(s, key=s.get),
            "positive_score": round(pos, 4),
            "negative_score": round(neg, 4),
            "neutral_score": round(neu, 4),
            "compound_score": round(pos - neg, 4),
            "model_used": "ProsusAI/finbert",
        })
    return results


class SentimentService:
    async def analyze(self, text: str) -> Dict:
        return (await self.analyze_batch([text]))[0]

    async def analyze_batch(self, texts: List[str]) -> List[Dict]:
        use_finbert = _finbert_state == "ready"
        model_tag = "finbert" if use_finbert else "lexicon"
        keys = [f"sentiment:{model_tag}:{hashlib.md5(t[:500].encode()).hexdigest()}" for t in texts]

        results: List[Optional[Dict]] = []
        for k in keys:
            results.append(await cache_get(k))

        todo = [i for i, r in enumerate(results) if r is None]
        if todo:
            pending = [texts[i] for i in todo]
            if use_finbert:
                try:
                    computed = await asyncio.to_thread(_finbert_batch, pending)
                except Exception as exc:
                    logger.warning("FinBERT inference failed (%s); falling back to lexicon", exc)
                    computed = [lexicon_sentiment(t) for t in pending]
            else:
                computed = [lexicon_sentiment(t) for t in pending]
            for i, res in zip(todo, computed):
                results[i] = res
                await cache_set(keys[i], res, ttl=86400)
        return results  # type: ignore[return-value]

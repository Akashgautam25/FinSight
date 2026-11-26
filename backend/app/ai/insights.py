"""
FinSight AI — AI insights (generative summaries embedded across the app)

    kind          shown on                  the LLM writes…
    ───────────   ───────────────────────   ─────────────────────────────────────────
    stock         stock detail page         an analyst note: summary, bull/bear case
    portfolio     portfolio page            a portfolio review: strengths, risks, ideas
    market        overview dashboard        today's market briefing from indices + news
    predictions   predictions page          a plain-language explanation of model results
    news          news page                 the key themes in the latest headlines

Each insight gathers fresh data with the agent's tools, asks the active LLM for a
short, grounded write-up (streamed token by token) and caches the result for 15
minutes. Without an LLM, a deterministic template produces the same sections.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional

from app.ai import llm
from app.ai.agent import DISCLAIMER, FinSightAgent, OfflineAnalyst
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger("finsight.insights")

KINDS = {"stock", "portfolio", "market", "predictions", "news"}

INSIGHT_SYSTEM = """You are FinSight AI, writing short insight cards for an educational investing web app.
Use ONLY the facts and numbers in the DATA section — never invent figures. Write clear markdown with bold
section labels and bullet points. Explain jargon in plain words for students. Never tell the reader to buy or sell.
If data is marked SIMULATED, say the figures are simulated demo data."""

PROMPTS = {
    "stock": ("Write an AI analyst note on {symbol}. Use exactly these sections: **Summary** (2 sentences), "
              "**Bull case** (2-3 bullets), **Bear case** (2-3 bullets), **What to watch** (1-2 bullets). Max 170 words."),
    "portfolio": ("Review this investor's portfolio. Sections: **Overview** (2 sentences on value, return and risk), "
                  "**Strengths** (2 bullets), **Risks** (2-3 bullets on concentration, volatility, drawdown), "
                  "**Ideas to consider** (2 educational bullets, no buy/sell instructions). Max 190 words."),
    "market": ("Write today's market briefing. Sections: **Market mood** (1-2 sentences on the indices), "
               "**Movers** (2 bullets on the biggest gainers/losers), **In the news** (2-3 bullets summarising headline themes "
               "and their sentiment). Max 150 words."),
    "predictions": ("Explain these machine-learning results for {symbol} to a student. Sections: **What the models say** "
                    "(forecast direction for short and long horizons, with the uncertainty), **How good are they?** (use skill vs naive "
                    "and directional accuracy; skill near 0 means no better than assuming the price stays the same), "
                    "**Takeaway** (1-2 sentences). Max 170 words."),
    "news": ("Summarise the latest news{about}. Sections: **Key themes** (3 bullets), **Sentiment** (1-2 sentences using the "
             "sentiment labels), **Why it matters** (1-2 sentences). Max 140 words."),
}


async def _gather(kind: str, symbol: Optional[str], agent: FinSightAgent) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if kind == "stock":
        await asyncio.gather(*(agent.run_tool(t, {"symbol": symbol}, data) for t in
                               ("get_stock_snapshot", "get_technical_analysis", "get_news_sentiment", "get_ml_forecast")))
    elif kind == "portfolio":
        await agent.run_tool("get_user_portfolio", {}, data)
    elif kind == "market":
        from app.services.news_service import NewsService
        await agent.run_tool("get_market_overview", {}, data)
        news = await NewsService().get_market_news(limit=8)
        data["headlines"] = news.get("articles", [])
    elif kind == "predictions":
        from app.services.prediction_service import PredictionService
        await agent.run_tool("get_ml_forecast", {"symbol": symbol}, data)
        data["evaluation"] = await PredictionService().get_evaluation_summary(symbol)
    elif kind == "news":
        if symbol:
            await agent.run_tool("get_news_sentiment", {"symbol": symbol}, data)
        else:
            from app.services.news_service import NewsService
            data["headlines"] = (await NewsService().get_market_news(limit=10)).get("articles", [])
    return data


def _format(data: Dict[str, Any]) -> str:
    parts = [FinSightAgent._format_item(k, v) for k, v in data.items() if ":" in k or k in ("portfolio", "market")]
    if data.get("headlines"):
        parts.append("### Latest headlines (with sentiment)\n" + "\n".join(
            f"- [{a.get('sentiment')}] {a['title']} ({a.get('source')})" for a in data["headlines"][:10]))
    ev = data.get("evaluation")
    if ev and ev.get("trained"):
        lines = []
        for row in ev.get("metrics", []):
            if row.get("error") or row["horizon_days"] not in (1, 5, 30):
                continue
            t = row["test"]
            lines.append(f"- {row['horizon_days']}d {row['model']}{' (best)' if row.get('is_best') else ''}: RMSE {t.get('rmse')}, "
                         f"MAPE {t.get('mape')}%, directional accuracy {t.get('directional_accuracy')}, skill vs naive {t.get('skill_vs_naive')}")
        parts.append(f"### Model evaluation on unseen test data (data: {ev.get('data_source')})\n" + "\n".join(lines))
    elif ev is not None:
        parts.append("### Model evaluation\nNo models have been trained for this stock yet.")
    return "\n\n".join(p for p in parts if p) or "No data available."


def _offline(kind: str, symbol: Optional[str], data: Dict[str, Any]) -> str:
    analyst = OfflineAnalyst(data, [symbol] if symbol else [], ["overview", "fundamental"], "")
    if kind == "stock":
        return analyst._stock(symbol)
    if kind == "portfolio":
        return analyst._portfolio()
    if kind == "market":
        heads = "\n".join(f"- [{a.get('sentiment')}] {a['title']}" for a in data.get("headlines", [])[:4])
        return analyst._market() + (f"\n\n**In the news**\n{heads}" if heads else "")
    if kind == "predictions":
        ev = data.get("evaluation") or {}
        best = [r for r in ev.get("metrics", []) if r.get("is_best") and not r.get("error")]
        if not best:
            return f"No models are trained for {symbol} yet — click **Train models** to generate forecasts and evaluation metrics."
        lines = [f"- **{r['horizon_days']}-day:** best model {r['model'].replace('_', ' ')} — directional accuracy "
                 f"{(r['test'].get('directional_accuracy') or 0) * 100:.1f}%, skill vs naive {(r['test'].get('skill_vs_naive') or 0) * 100:+.1f}%"
                 for r in best]
        return ("**How good are the models?**\n" + "\n".join(lines) +
                "\n\n**Takeaway:** skill close to zero means the models are about as accurate as assuming tomorrow's price equals "
                "today's — typical for liquid stocks. Treat forecasts as uncertain estimates.")
    if kind == "news":
        s = next((v for k, v in data.items() if k.startswith("sentiment:")), None)
        arts = (s or {}).get("headlines") or data.get("headlines", [])
        counts = {lbl: sum(1 for a in arts if a.get("sentiment") == lbl) for lbl in ("positive", "neutral", "negative")}
        heads = "\n".join(f"- [{a.get('sentiment')}] {a['title']}" for a in arts[:5])
        return f"**Sentiment:** {counts['positive']} positive · {counts['neutral']} neutral · {counts['negative']} negative headlines\n\n**Latest**\n{heads}"
    return ""


async def stream_insight(kind: str, symbol: Optional[str], user_id: Optional[str], refresh: bool = False) -> AsyncIterator[dict]:
    symbol = symbol.upper() if symbol else None
    providers = await llm.available_providers()
    provider_label = providers[0].label if providers else "offline"
    owner = user_id if kind == "portfolio" else "all"
    cache_key = f"insight:{kind}:{symbol or '-'}:{owner}:{provider_label}"

    if not refresh:
        cached = await cache_get(cache_key)
        if cached:
            yield {"type": "token", "text": cached["text"]}
            yield {"type": "done", "provider": cached["provider"], "cached": True, "generated_at": cached["generated_at"]}
            return

    yield {"type": "status", "message": "Gathering data"}
    data = await _gather(kind, symbol, FinSightAgent(user_id=user_id))
    is_demo = any(isinstance(v, dict) and v.get("is_demo") for v in data.values())
    prompt = PROMPTS[kind].format(symbol=symbol or "", about=f" about {symbol}" if symbol else " in the markets")
    messages = [{"role": "system", "content": INSIGHT_SYSTEM},
                {"role": "user", "content": f"DATA:\n{_format(data)}\n\nTASK: {prompt}"}]

    parts, used = [], "offline"
    for provider in providers:
        yield {"type": "status", "message": f"Writing with {provider.label}"}
        try:
            async for ev in llm.stream_chat(provider, messages, None, temperature=0.3, max_tokens=450):
                if ev["type"] == "token":
                    parts.append(ev["text"])
                    yield ev
            if "".join(parts).strip():
                used = provider.label
                break
        except Exception as exc:
            logger.warning("Insight via %s failed: %s", provider.label, exc)
            if parts:
                used = provider.label
                break

    if not "".join(parts).strip():
        text = _offline(kind, symbol, data)
        parts = [text]
        yield {"type": "token", "text": text}
    if is_demo and "simulated" not in "".join(parts).lower():
        note = "\n\n_Figures are simulated demo data._"
        parts.append(note)
        yield {"type": "token", "text": note}

    generated_at = datetime.now(timezone.utc).isoformat()
    await cache_set(cache_key, {"text": "".join(parts), "provider": used, "generated_at": generated_at}, ttl=900)
    yield {"type": "done", "provider": used, "cached": False, "generated_at": generated_at, "disclaimer": DISCLAIMER}

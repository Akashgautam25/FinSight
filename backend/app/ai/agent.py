"""
FinSight AI — Financial Research Agent (tool-using, streaming)

Pipeline
  1. Plan      — extract tickers & intents from the question (+ conversation memory)
  2. Retrieve  — call data tools in parallel (quotes, technicals, news sentiment,
                 ML forecasts, the user's portfolio, market overview) and semantic
                 search over the financial knowledge base  → VERIFIED DATA
  3. Reason    — an LLM (Gemini / Groq / OpenAI / local Ollama) answers from the
                 verified data and may call further tools itself (native function
                 calling, up to 2 extra rounds)
  4. Stream    — every step is emitted as an event: tool started/finished, answer
                 tokens, then sources + follow-up suggestions

Guarantees
  * Numbers come from tools, never from the model's memory (enforced by the prompt).
  * Always answers: with no LLM available an offline analyst composes a
    structured, data-grounded answer from the same tool results.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from app.ai import llm
from app.ai.knowledge_base import aretrieve
from app.data import market_data as md
from app.data.providers.demo_provider import DEMO_STOCKS

logger = logging.getLogger("finsight.agent")

DISCLAIMER = "⚠️ Educational information only — not financial advice."

COMPANY_ALIASES = {
    "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "meta": "META", "facebook": "META", "tesla": "TSLA", "netflix": "NFLX",
    "amd": "AMD", "intel": "INTC", "jpmorgan": "JPM", "jp morgan": "JPM", "bank of america": "BAC",
    "visa": "V", "mastercard": "MA", "johnson & johnson": "JNJ", "pfizer": "PFE", "exxon": "XOM",
    "walmart": "WMT", "coca-cola": "KO", "coca cola": "KO", "disney": "DIS", "berkshire": "BRK-B",
    "broadcom": "AVGO", "oracle": "ORCL", "salesforce": "CRM", "adobe": "ADBE", "ibm": "IBM",
    "reliance": "RELIANCE.NS", "tcs": "TCS.NS", "tata consultancy": "TCS.NS", "infosys": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS", "hdfc": "HDFCBANK.NS", "icici": "ICICIBANK.NS", "wipro": "WIPRO.NS",
    "tata motors": "TATAMOTORS.NS", "itc": "ITC.NS", "airtel": "BHARTIARTL.NS", "sbi": "SBIN.NS",
}

NOT_TICKERS = {
    "I", "A", "AI", "ML", "PE", "P", "E", "RSI", "MACD", "ETF", "ETFS", "CEO", "CFO", "USD", "INR", "EUR", "EPS",
    "IPO", "GDP", "FED", "SEC", "NYSE", "NSE", "BSE", "ROE", "ROA", "VAR", "CVAR", "YOY", "QOQ", "EBITDA", "DCF",
    "OK", "THE", "AND", "OR", "FOR", "IN", "ON", "AT", "IS", "ARE", "BE", "MY", "ME", "US", "UK", "EU", "TO",
    "OF", "IT", "DO", "VS", "SMA", "EMA", "ATR", "LSTM", "NLP", "API", "FAQ", "ESG", "FCF", "DE", "MPT", "ATH",
    "WHAT", "HOW", "WHY", "WHO", "WHEN", "SHOULD", "BUY", "SELL", "HOLD", "NOW", "TODAY", "CAN", "YOU", "TELL",
    "SIP", "NAV", "IRR", "CAGR", "ROI", "PEG", "Q1", "Q2", "Q3", "Q4", "FY", "AM", "PM", "UTC", "EST", "IST",
}

TICKER_RE = re.compile(r"\$?\b([A-Z]{1,5}(?:[.-][A-Z]{1,2})?)\b")
INDEX_WORDS = {"s&p": "^GSPC", "s&p 500": "^GSPC", "nasdaq": "^IXIC", "dow": "^DJI", "nifty": "^NSEI", "sensex": "^BSESN"}

INTENT_KEYWORDS = {
    "technical": ["rsi", "macd", "technical", "bollinger", "moving average", "sma", "ema", "trend", "momentum", "overbought", "oversold", "chart", "support", "resistance"],
    "fundamental": ["p/e", "pe ratio", "valuation", "fundamental", "earnings", "eps", "dividend", "margin", "roe", "debt", "market cap", "revenue", "cash flow", "expensive", "cheap", "undervalued", "overvalued"],
    "news": ["news", "sentiment", "headline", "latest", "happening", "announcement", "why is", "why did"],
    "prediction": ["predict", "forecast", "future", "target", "next week", "next month", "will it", "outlook", "price in"],
    "compare": ["compare", " vs ", "versus", "better than", "or "],
    "portfolio": ["my portfolio", "my holdings", "my stocks", "portfolio", "my investments", "diversif", "risk of my", "rebalance"],
    "market": ["market today", "market overview", "indices", "index", "how is the market", "top gainers", "top losers", "movers"],
    "education": ["what is", "what are", "explain", "define", "meaning", "how does", "how do", "difference between", "tell me about"],
}

SYSTEM_PROMPT = """You are FinSight AI, a financial research assistant inside an educational web app for students.

Rules:
- Use ONLY facts and numbers from the VERIFIED DATA and tool results. Never invent prices, ratios, dates or forecasts.
- If you need data that is not provided, call a tool (for example get_ml_forecast, get_user_portfolio, compare_stocks).
  Do not call a tool for data that is already in VERIFIED DATA.
- Write concise markdown (about 120-200 words unless asked for more): a short heading, bullet points, plain-language explanations of jargon.
- Separate facts from interpretation (label it "Interpretation"). Never tell the user to buy or sell.
- If data is marked SIMULATED, say the figures are simulated demo data.
- When citing a forecast, mention its 95% interval and that forecasts are uncertain.
- Interpretation guide: P/E below 15 = low, 15-30 = moderate, above 30 = high (compare within the sector);
  RSI above 70 = overbought, below 30 = oversold; beta above 1 = more volatile than the market;
  Sharpe above 1 = good risk-adjusted return; a lower P/E does NOT mean "expensive".
- Finish with: "⚠️ Educational information only — not financial advice." """

SYMBOL_PARAM = {"type": "string", "description": "Ticker symbol, e.g. AAPL, MSFT, NVDA. Indian stocks use .NS, e.g. RELIANCE.NS"}
TOOLS = [
    {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": list(props)}}}
    for name, desc, props in [
        ("get_stock_snapshot", "Latest price, daily change and fundamentals (P/E, market cap, beta, margins) for one stock.", {"symbol": SYMBOL_PARAM}),
        ("get_technical_analysis", "Technical indicators (RSI, MACD, moving averages, Bollinger Bands) and their bullish/bearish signals for one stock.", {"symbol": SYMBOL_PARAM}),
        ("get_news_sentiment", "Recent news headlines and aggregated news sentiment for one stock.", {"symbol": SYMBOL_PARAM}),
        ("get_ml_forecast", "Machine-learning price forecasts for 1, 5, 10 and 30 days with 95% intervals (only if models were trained).", {"symbol": SYMBOL_PARAM}),
        ("get_user_portfolio", "The user's own portfolio: holdings, value, profit/loss and risk metrics.", {}),
        ("get_market_overview", "Major stock index levels and today's top gaining and losing stocks.", {}),
        ("compare_stocks", "Side-by-side fundamentals and technical signals for 2 to 4 stocks.",
         {"symbols": {"type": "array", "items": {"type": "string"}, "description": "2-4 ticker symbols"}}),
        ("search_financial_knowledge", "Explanations of financial concepts: ratios, indicators, risk metrics, portfolio theory, ML models.",
         {"query": {"type": "string", "description": "The concept to look up"}}),
    ]
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


def _fmt_money(v: Optional[float], currency: str = "USD") -> str:
    if v is None:
        return "n/a"
    symbol = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(currency, "")
    return f"{symbol}{v:,.2f}" if symbol else f"{v:,.2f} {currency}"


def _fmt_big(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(v) >= div:
            return f"{v / div:.2f}{suffix}"
    return f"{v:,.0f}"


def _pct(v: Optional[float], already_pct: bool = False, digits: int = 2) -> str:
    if v is None:
        return "n/a"
    return f"{v if already_pct else v * 100:.{digits}f}%"


class FinSightAgent:
    def __init__(self, db=None, user_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id

    # ── Planning ─────────────────────────────────────────────────────────────
    async def extract_symbols(self, text: str) -> List[str]:
        """Find tickers mentioned in the text, in order of appearance (max 4)."""
        hits: List[Tuple[int, str, bool]] = []  # (position, symbol, needs_validation)
        lowered = text.lower()
        masked = lowered
        for alias in sorted(COMPANY_ALIASES, key=len, reverse=True):  # longest first: "bank of america" before "bank"
            for m in re.finditer(rf"\b{re.escape(alias)}\b", masked):
                hits.append((m.start(), COMPANY_ALIASES[alias], False))
                masked = masked[:m.start()] + " " * len(alias) + masked[m.end():]

        for m in TICKER_RE.finditer(text):
            tok = m.group(1).upper()
            explicit = m.group(0).startswith("$")
            if (tok in NOT_TICKERS or len(tok) == 1) and not explicit:
                continue
            hits.append((m.start(), tok, tok not in DEMO_STOCKS))

        # Lower-case tickers of well-known stocks ("nvda", "aapl")
        for m in re.finditer(r"\b[a-z]{3,5}\b", text):
            if m.group(0).upper() in DEMO_STOCKS:
                hits.append((m.start(), m.group(0).upper(), False))

        ordered: List[Tuple[str, bool]] = []
        for _, sym, validate in sorted(hits):
            if sym not in [o[0] for o in ordered]:
                ordered.append((sym, validate))

        to_check = [sym for sym, validate in ordered if validate][:5]
        valid_unknown: set = set()
        if to_check:
            try:
                quotes = await md.aquotes(to_check)
                valid_unknown = {u for u in to_check if u in quotes and not quotes[u]["is_demo"]}
            except Exception:
                pass
        return [sym for sym, validate in ordered if not validate or sym in valid_unknown][:4]

    @staticmethod
    def detect_intents(text: str, symbols: List[str]) -> List[str]:
        t = f" {text.lower()} "
        intents = [name for name, words in INTENT_KEYWORDS.items() if any(w in t for w in words)]
        if "compare" in intents and len(symbols) < 2:
            intents.remove("compare")
        if len(symbols) >= 2 and "compare" not in intents and any(w in t for w in (" vs", "versus", "compare", " or ", "better")):
            intents.append("compare")
        if symbols and not set(intents) & {"technical", "fundamental", "news", "prediction", "compare"}:
            intents.append("overview")
        if not intents:
            intents.append("education" if not symbols else "overview")
        return intents

    # ── Data tools ───────────────────────────────────────────────────────────
    async def tool_stock(self, symbol: str):
        from app.services.stock_service import StockService
        d = await StockService().get_stock_detail(symbol)
        return d.model_dump(mode="json") if d else None

    async def tool_technicals(self, symbol: str):
        from app.services.stock_service import StockService
        try:
            return (await StockService().get_technical_indicators(symbol)).model_dump(mode="json")
        except ValueError:
            return None

    async def tool_sentiment(self, symbol: str):
        from app.services.news_service import NewsService
        svc = NewsService()
        summary = await svc.get_sentiment_summary(symbol, days=14)
        news = await svc.get_stock_news(symbol, limit=5, days=14)
        summary["headlines"] = [
            {"title": a["title"], "url": a.get("url"), "source": a.get("source"), "sentiment": a.get("sentiment"),
             "published_at": a.get("published_at")}
            for a in news.get("articles", [])[:5]
        ]
        return summary

    async def tool_predictions(self, symbol: str):
        from app.services.prediction_service import PredictionService
        return await PredictionService().get_predictions(symbol)

    async def tool_portfolio(self):
        if not self.user_id:
            return None
        from sqlalchemy import select

        from app.database import AsyncSessionLocal
        from app.models import Portfolio
        from app.services.portfolio_service import PortfolioService

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Portfolio).where(Portfolio.user_id == self.user_id).order_by(Portfolio.is_default.desc(), Portfolio.created_at))
            portfolio = res.scalars().first()
            if not portfolio:
                return {"empty": True}
            analytics = await PortfolioService(db).compute_analytics(portfolio)
            data = analytics.model_dump(mode="json")
            data["name"] = portfolio.name
        data.pop("performance", None)
        return data

    async def tool_market(self):
        from app.services.stock_service import StockService
        return (await StockService().get_market_overview()).model_dump(mode="json")

    @staticmethod
    def _sym(value) -> str:
        return re.sub(r"[^A-Z0-9.\-^]", "", str(value or "").upper())[:20]

    async def run_tool(self, name: str, args: dict, data: Dict[str, Any]) -> Tuple[str, str]:
        """Execute one tool. Stores raw results in `data`; returns (ui_summary, text_for_llm)."""
        try:
            if name in ("get_stock_snapshot", "get_technical_analysis", "get_news_sentiment", "get_ml_forecast"):
                sym = self._sym(args.get("symbol"))
                if not sym:
                    return "missing symbol", "Error: a ticker symbol is required."
                kind, fn = {
                    "get_stock_snapshot": ("stock", self.tool_stock),
                    "get_technical_analysis": ("technicals", self.tool_technicals),
                    "get_news_sentiment": ("sentiment", self.tool_sentiment),
                    "get_ml_forecast": ("predictions", self.tool_predictions),
                }[name]
                key = f"{kind}:{sym}"
                if key not in data:
                    value = await asyncio.wait_for(fn(sym), timeout=45)
                    if value is None:
                        if kind == "predictions":
                            return "no trained models", f"No ML models are trained for {sym} yet. Tell the user to train them on the Predictions page."
                        return "no data", f"No data found for {sym}."
                    data[key] = value
                return self._summary(key, data[key]), self._format_item(key, data[key])
            if name == "get_user_portfolio":
                if "portfolio" not in data:
                    value = await asyncio.wait_for(self.tool_portfolio(), timeout=45)
                    if value is None:
                        return "unavailable", "The user's portfolio is not available."
                    data["portfolio"] = value
                return self._summary("portfolio", data["portfolio"]), self._format_item("portfolio", data["portfolio"])
            if name == "get_market_overview":
                if "market" not in data:
                    data["market"] = await asyncio.wait_for(self.tool_market(), timeout=45)
                return self._summary("market", data["market"]), self._format_item("market", data["market"])
            if name == "compare_stocks":
                syms = [self._sym(x) for x in (args.get("symbols") or [])][:4]
                syms = [x for x in syms if x]
                if len(syms) < 2:
                    return "need 2+ symbols", "Error: provide at least two ticker symbols."
                await asyncio.gather(*(self.run_tool(t, {"symbol": x}, data) for x in syms for t in ("get_stock_snapshot", "get_technical_analysis")))
                parts = [self._format_item(k, data[k]) for x in syms for k in (f"stock:{x}", f"technicals:{x}") if k in data]
                return f"{len(syms)} stocks", "\n\n".join(parts) or "No data found."
            if name == "search_financial_knowledge":
                docs = await aretrieve(str(args.get("query", "")), k=2)
                known = {d["title"] for d in data.get("knowledge", [])}
                data.setdefault("knowledge", []).extend(d for d in docs if d["title"] not in known)
                if not docs:
                    return "no matches", "No relevant knowledge-base entries."
                return ", ".join(d["title"] for d in docs), "\n\n".join(f"{d['title']}: {d['content']}" for d in docs)
            return "unknown tool", f"Error: unknown tool {name}."
        except asyncio.TimeoutError:
            return "timed out", f"Error: {name} timed out."
        except Exception as exc:
            logger.info("Tool %s failed: %s", name, exc)
            return "failed", f"Error: {name} failed."

    @staticmethod
    def _summary(key: str, v: Any) -> str:
        kind, _, sym = key.partition(":")
        try:
            if kind == "stock":
                chg = v.get("change_pct")
                return f"{v['name']} · {v.get('current_price')} {v.get('currency')}" + (f" ({chg:+.2f}%)" if chg is not None else "")
            if kind == "technicals":
                return f"{v.get('overall_signal')} · RSI {v.get('rsi_14', 0):.1f}"
            if kind == "sentiment":
                return f"{v.get('overall_sentiment')} · {v.get('news_count')} articles"
            if kind == "predictions":
                return f"best model {v.get('best_model')} · {len(v.get('forecast_path', []))} horizons"
            if kind == "portfolio":
                return "no portfolio yet" if v.get("empty") else f"value {v.get('current_value'):,.0f} · Sharpe {v.get('sharpe_ratio')}"
            if kind == "market":
                spx = next((i for i in v.get("indices", []) if i["symbol"] == "^GSPC"), None)
                return f"S&P 500 {spx['change_pct']:+.2f}%" if spx else "indices & movers"
        except Exception:
            pass
        return "ok"

    def _plan(self, symbols: List[str], intents: List[str], question: str) -> List[Tuple[str, dict]]:
        calls: List[Tuple[str, dict]] = []
        for s in symbols:
            calls.append(("get_stock_snapshot", {"symbol": s}))
            if {"technical", "overview", "compare"} & set(intents):
                calls.append(("get_technical_analysis", {"symbol": s}))
            if {"news", "overview"} & set(intents):
                calls.append(("get_news_sentiment", {"symbol": s}))
            if "prediction" in intents:
                calls.append(("get_ml_forecast", {"symbol": s}))
        if "portfolio" in intents:
            calls.append(("get_user_portfolio", {}))
        if "market" in intents or (not symbols and "portfolio" not in intents and "education" not in intents):
            calls.append(("get_market_overview", {}))
        calls.append(("search_financial_knowledge", {"query": question}))
        return calls

    # ── Context & citations ──────────────────────────────────────────────────
    @staticmethod
    def _format_item(key: str, val: Any) -> str:
        if not val:
            return ""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        kind, _, sym = key.partition(":")
        tag = " [SIMULATED DATA]" if isinstance(val, dict) and val.get("is_demo") else ""
        if kind == "stock":
            m = val.get("metrics") or {}
            cur = val.get("currency", "USD")
            chg = val.get("change_pct")
            fields = [
                ("Company", val.get("name")), ("Sector", val.get("sector")),
                ("Price", _fmt_money(val.get("current_price"), cur)),
                ("Change today", f"{chg:+.2f}%" if chg is not None else None),
                ("52-week range", f"{_fmt_money(m.get('week_52_low'), cur)} to {_fmt_money(m.get('week_52_high'), cur)}" if m.get("week_52_low") else None),
                ("Market cap", _fmt_big(m.get("market_cap")) if m.get("market_cap") else None),
                ("P/E ratio", f"{m['pe_ratio']:.1f}" if m.get("pe_ratio") else None),
                ("EPS", m.get("eps")), ("Beta", m.get("beta")),
                ("Dividend yield", _pct(m.get("dividend_yield")) if m.get("dividend_yield") is not None else None),
                ("Return on equity", _pct(m.get("roe"), digits=1) if m.get("roe") is not None else None),
                ("Profit margin", _pct(m.get("profit_margin"), digits=1) if m.get("profit_margin") is not None else None),
                ("Revenue growth (YoY)", _pct(m.get("revenue_growth"), digits=1) if m.get("revenue_growth") is not None else None),
                ("Debt-to-equity", f"{m['debt_to_equity']:.2f}x" if m.get("debt_to_equity") is not None else None),
            ]
            return f"### {sym} quote & fundamentals{tag} (fetched {now})\n" + "\n".join(f"- {k}: {v}" for k, v in fields if v not in (None, ""))
        if kind == "technicals":
            sig = "; ".join(f"{s['indicator']}: {s['signal']} ({s['detail']})" for s in val.get("signals", []))
            return (
                f"### {sym} technical indicators{tag} (as of {val.get('date')})\n"
                f"close={val.get('close')}; rsi_14={val.get('rsi_14')}; macd={val.get('macd')}; macd_signal={val.get('macd_signal')}; "
                f"sma_20={val.get('sma_20')}; sma_50={val.get('sma_50')}; sma_200={val.get('sma_200')}; "
                f"bb_upper={val.get('bb_upper')}; bb_lower={val.get('bb_lower')}; volatility_30d_annualized_pct={val.get('volatility_30d')}; "
                f"overall_signal={val.get('overall_signal')}\nsignals: {sig}"
            )
        if kind == "sentiment":
            heads = "\n".join(f"- [{h.get('sentiment')}] {h['title']} ({h.get('source')})" for h in val.get("headlines", []))
            return (
                f"### {sym} news sentiment{tag} (last {val.get('period_days')} days, model={val.get('sentiment_model')})\n"
                f"overall={val.get('overall_sentiment')}; positive={val.get('positive_pct')}%; negative={val.get('negative_pct')}%; "
                f"neutral={val.get('neutral_pct')}%; articles={val.get('news_count')}; avg_compound={val.get('avg_compound_score')}\n{heads}"
            )
        if kind == "predictions":
            lines = [f"- {pt['horizon']} (best model {pt['model']}): {pt['predicted']} (95% interval {pt['lower']}–{pt['upper']})"
                     for pt in val.get("forecast_path", [])]
            return f"### {sym} ML forecasts{tag} (trained {val.get('trained_at', '')[:10]}, current price {val.get('current_price')})\n" + "\n".join(lines)
        if kind == "portfolio":
            if val.get("empty"):
                return "### User portfolio\nThe user has no portfolio yet."
            holds = "\n".join(
                f"- {h['symbol']}: weight {h.get('weight')}%, unrealized P&L {h.get('unrealized_pnl')} ({h.get('unrealized_pnl_pct')}%), sector {h.get('sector')}"
                for h in val.get("holdings", [])
            )
            return (
                f"### User portfolio '{val.get('name')}'{tag}\n"
                f"value={val.get('current_value')}; invested={val.get('total_invested')}; return_pct={val.get('return_pct')}; "
                f"realized_pnl={val.get('realized_pnl')}; annualized_return_pct={val.get('annualized_return')}; volatility_pct={val.get('portfolio_volatility')}; "
                f"sharpe={val.get('sharpe_ratio')}; sortino={val.get('sortino_ratio')}; max_drawdown_pct={val.get('max_drawdown')}; beta={val.get('beta')}; "
                f"var95_1day={val.get('var_95')}; cvar95_1day={val.get('cvar_95')}; sectors={val.get('sector_allocation')}\n{holds}"
            )
        if kind == "market":
            idx = "; ".join(f"{i['name']} {i['value']} ({i['change_pct']}%)" for i in val.get("indices", []))
            g = ", ".join(f"{m['symbol']} {m['change_pct']}%" for m in val.get("top_gainers", []))
            lo = ", ".join(f"{m['symbol']} {m['change_pct']}%" for m in val.get("top_losers", []))
            return f"### Market overview{tag} (US market {val.get('market_status')})\nindices: {idx}\ntop gainers: {g}\ntop losers: {lo}"
        return ""

    @classmethod
    def _context(cls, data: Dict[str, Any]) -> str:
        parts = [cls._format_item(k, v) for k, v in data.items() if k != "knowledge"]
        parts += [f"### Knowledge base: {d['title']}\n{d['content']}" for d in data.get("knowledge", [])]
        parts = [p for p in parts if p]
        return "\n\n".join(parts) if parts else "No market data was retrieved for this question."

    @staticmethod
    def _sources(data: Dict[str, Any]) -> List[dict]:
        now = datetime.now(timezone.utc).isoformat()
        labels = {"stock": ("market_data", "{s} quote & fundamentals"), "technicals": ("technicals", "{s} technical indicators"),
                  "sentiment": ("news", "{s} news sentiment"), "predictions": ("prediction", "{s} ML model forecasts")}
        out = []
        for key, val in data.items():
            kind, _, sym = key.partition(":")
            if kind in labels:
                t, title = labels[kind]
                src = "simulated data" if isinstance(val, dict) and val.get("is_demo") else "Yahoo Finance" if kind != "predictions" else "FinSight models"
                out.append({"type": t, "title": f"{title.format(s=sym)} · {src}", "url": f"/stocks/{sym}", "timestamp": now, "is_verified": True})
                if kind == "sentiment":
                    for h in (val.get("headlines") or [])[:3]:
                        if h.get("url"):
                            out.append({"type": "news", "title": h["title"], "url": h["url"], "timestamp": h.get("published_at"), "is_verified": True})
            elif kind == "portfolio":
                out.append({"type": "portfolio", "title": "Your portfolio analytics", "url": "/portfolio", "timestamp": now, "is_verified": True})
            elif kind == "market":
                out.append({"type": "market_data", "title": "Market overview · indices & movers", "url": "/market", "timestamp": now, "is_verified": True})
        for doc in data.get("knowledge", []):
            out.append({"type": "knowledge_base", "title": f"Knowledge base: {doc['title']}", "url": None, "timestamp": None, "is_verified": True})
        return out

    @staticmethod
    def _suggestions(symbols: List[str], intents: List[str]) -> List[str]:
        if symbols:
            s = symbols[0]
            options = [f"What do the technical indicators say about {s}?", f"Summarise recent news sentiment for {s}",
                       f"Show the ML forecast for {s}", f"Is {s}'s valuation high compared to its earnings?"]
            if len(symbols) == 1:
                options.append(f"Compare {s} with {'MSFT' if s != 'MSFT' else 'AAPL'}")
            skip = {"news": "news", "prediction": "forecast", "technical": "technical"}
            return [o for o in options if not any(word in o.lower() for intent, word in skip.items() if intent in intents)][:3]
        return ["How is the market doing today?", "Analyse the risk of my portfolio", "What is the Sharpe ratio?"]

    # ── Main entry points ────────────────────────────────────────────────────
    async def stream(self, message: str, history: Optional[List[dict]] = None) -> AsyncIterator[dict]:
        """Yield agent events: status, tool (running/done), token, done."""
        history = history or []
        yield {"type": "status", "message": "Understanding your question"}
        symbols = await self.extract_symbols(message)
        if not symbols and history:
            # Follow-up questions ("what about its RSI?") reuse the previous symbols
            for prev in reversed([m for m in history if m["role"] == "user"][-3:]):
                symbols = await self.extract_symbols(prev["content"])
                if symbols:
                    break
        intents = self.detect_intents(message, symbols)

        data: Dict[str, Any] = {}
        tool_log: List[str] = []

        # Step 2 — deterministic retrieval, run in parallel, streamed as each finishes
        yield {"type": "status", "message": "Retrieving verified data"}
        plan = self._plan(symbols, intents, message)
        tasks = {}
        for i, (name, args) in enumerate(plan):
            call_id = f"plan-{i}"
            yield {"type": "tool", "id": call_id, "name": name, "args": args, "status": "running"}
            tool_log.append(self._log_name(name, args))

            async def _run(cid=call_id, n=name, a=args):
                return cid, n, a, await self.run_tool(n, a, data)
            tasks[call_id] = asyncio.create_task(_run())
        for fut in asyncio.as_completed(list(tasks.values())):
            cid, name, args, (summary, _) = await fut
            yield {"type": "tool", "id": cid, "name": name, "args": args, "status": "done", "summary": summary}

        # Step 3 — reasoning with an LLM (with optional extra tool calls)
        provider_used = "offline"
        answer_parts: List[str] = []
        providers = await llm.available_providers()
        if providers:
            yield {"type": "status", "message": "Thinking"}
            base_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            base_messages += [{"role": m["role"], "content": m["content"][:1500]} for m in history[-6:] if m.get("content")]
            base_messages.append({"role": "user", "content": (
                f"VERIFIED DATA:\n{self._context(data)}\n\nQUESTION: {message}\n\n"
                "(Answer in under 200 words using the data above.)")})
            for provider in providers:
                messages = list(base_messages)
                try:
                    for round_no in range(3):
                        calls = None
                        async for ev in llm.stream_chat(provider, messages, tools=TOOLS if round_no < 2 else None, max_tokens=700):
                            if ev["type"] == "token":
                                answer_parts.append(ev["text"])
                                yield ev
                            elif ev["type"] == "tool_calls":
                                calls = [c for c in ev["calls"] if c["name"] in TOOL_NAMES]
                        if not calls:
                            break
                        messages.append({"role": "assistant", "content": "", "tool_calls": calls})
                        for c in calls:
                            yield {"type": "tool", "id": c["id"], "name": c["name"], "args": c["arguments"], "status": "running", "by_model": True}
                            summary, text = await self.run_tool(c["name"], c["arguments"], data)
                            tool_log.append(self._log_name(c["name"], c["arguments"]))
                            yield {"type": "tool", "id": c["id"], "name": c["name"], "args": c["arguments"], "status": "done", "summary": summary, "by_model": True}
                            messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": text[:4000]})
                    if "".join(answer_parts).strip():
                        provider_used = provider.label
                        break
                except Exception as exc:
                    logger.warning("LLM provider %s failed: %s", provider.label, exc)
                    if answer_parts:  # already streamed partial output — finish gracefully
                        provider_used = provider.label
                        note = "\n\n_(The AI response was interrupted.)_"
                        answer_parts.append(note)
                        yield {"type": "token", "text": note}
                        break

        if not "".join(answer_parts).strip():
            # Offline analyst — stream in small chunks for a consistent UX
            text = OfflineAnalyst(data, symbols, intents, message).compose()
            for chunk in re.findall(r"\S+\s*", text):
                answer_parts.append(chunk)
                yield {"type": "token", "text": chunk}
                await asyncio.sleep(0.004)
        elif "not financial advice" not in "".join(answer_parts).lower():
            tail = f"\n\n{DISCLAIMER}"
            answer_parts.append(tail)
            yield {"type": "token", "text": tail}

        yield {
            "type": "done",
            "content": "".join(answer_parts),
            "sources": self._sources(data),
            "tool_calls": tool_log,
            "llm_provider": provider_used,
            "symbols": symbols,
            "intents": intents,
            "suggestions": self._suggestions(symbols, intents),
        }

    @staticmethod
    def _log_name(name: str, args: dict) -> str:
        if "symbol" in args:
            return f"{name}({args['symbol']})"
        if "symbols" in args:
            return f"{name}({', '.join(map(str, args['symbols']))})"
        if "query" in args:
            return f"{name}()"
        return f"{name}()"

    async def run(self, message: str, history: Optional[List[dict]] = None) -> Dict[str, Any]:
        """Non-streaming convenience wrapper around `stream`."""
        result: Dict[str, Any] = {}
        async for event in self.stream(message, history):
            if event["type"] == "done":
                result = event
        return result


class OfflineAnalyst:
    """Deterministic, data-grounded answer composer used when no LLM is available."""

    def __init__(self, data: Dict[str, Any], symbols: List[str], intents: List[str], question: str):
        self.data, self.symbols, self.intents, self.question = data, symbols, intents, question

    def compose(self) -> str:
        sections: List[str] = []
        if "compare" in self.intents and len(self.symbols) >= 2:
            sections.append(self._compare())
        else:
            for s in self.symbols:
                sections.append(self._stock(s))
        if "portfolio" in self.intents:
            sections.append(self._portfolio())
        if "market" in self.data:
            sections.append(self._market())
        knowledge = self.data.get("knowledge") or []
        if knowledge and ("education" in self.intents or not sections):
            sections.append("\n\n".join(f"### 📘 {d['title']}\n{d['content']}" for d in knowledge))
        if not [s for s in sections if s]:
            sections.append(
                "I couldn't find a stock symbol or a topic I have data on in that question. Try asking about a ticker "
                "(e.g. *“How is NVDA doing?”*), your portfolio (*“Analyse my portfolio risk”*), the market today, "
                "or a concept such as *“What is the Sharpe ratio?”*."
            )
        if any(isinstance(v, dict) and v.get("is_demo") for v in self.data.values()):
            sections.append("> ℹ️ Some figures above are **simulated demo data** because live market data was unavailable.")
        sections.append("_Offline analyst mode — start Ollama or add `GOOGLE_API_KEY` for AI-written answers._\n\n" + DISCLAIMER)
        return "\n\n".join(s for s in sections if s)

    def _stock(self, s: str) -> str:
        d = self.data.get(f"stock:{s}")
        if not d:
            return f"### {s}\nI couldn't retrieve market data for **{s}**."
        m = d.get("metrics") or {}
        cur = d.get("currency", "USD")
        out = [f"### {d['name']} ({s})"]
        change = d.get("change_pct")
        arrow = "▲" if (change or 0) >= 0 else "▼"
        out.append(f"**Price:** {_fmt_money(d.get('current_price'), cur)} {arrow} {_pct(change, True) if change is not None else ''} today · "
                   f"Day range {_fmt_money(d.get('day_low'), cur)} – {_fmt_money(d.get('day_high'), cur)}")
        hi, lo, price = m.get("week_52_high"), m.get("week_52_low"), d.get("current_price")
        if hi and lo and price and hi > lo:
            pos = (price - lo) / (hi - lo) * 100
            out.append(f"**52-week range:** {_fmt_money(lo, cur)} – {_fmt_money(hi, cur)} (currently at {pos:.0f}% of the range)")

        if {"fundamental", "overview", "compare"} & set(self.intents):
            bullets = [f"- Market cap: {_fmt_big(m.get('market_cap'))}"]
            pe = m.get("pe_ratio")
            if pe:
                view = "a premium valuation — investors expect strong growth" if pe > 30 else "a moderate valuation" if pe > 15 else "a relatively low valuation"
                bullets.append(f"- P/E ratio: **{pe:.1f}** → {view}")
            if m.get("beta") is not None:
                b = m["beta"]
                bullets.append(f"- Beta: {b:.2f} → {'more volatile than' if b > 1.1 else 'less volatile than' if b < 0.9 else 'moves roughly with'} the market")
            if m.get("profit_margin") is not None:
                bullets.append(f"- Profit margin: {_pct(m['profit_margin'])}")
            if m.get("roe") is not None:
                bullets.append(f"- Return on equity: {_pct(m['roe'])}")
            if m.get("dividend_yield"):
                bullets.append(f"- Dividend yield: {_pct(m['dividend_yield'])}")
            out.append("**Fundamentals**\n" + "\n".join(bullets))

        t = self.data.get(f"technicals:{s}")
        if t:
            sig = "\n".join(f"- {x['indicator']}: *{x['signal']}* — {x['detail']}" for x in t.get("signals", []))
            out.append(f"**Technicals** (overall: **{t.get('overall_signal')}**, 30-day volatility {t.get('volatility_30d') or 'n/a'}% annualized)\n{sig}")

        se = self.data.get(f"sentiment:{s}")
        if se and se.get("news_count"):
            lines = [f"**News sentiment** ({se['news_count']} articles, {se.get('sentiment_model')}): **{se['overall_sentiment']}** — "
                     f"{se['positive_pct']}% positive, {se['negative_pct']}% negative, {se['neutral_pct']}% neutral"]
            for h in (se.get("headlines") or [])[:3]:
                lines.append(f"- [{h.get('sentiment')}] {h['title']}")
            out.append("\n".join(lines))

        if "prediction" in self.intents:
            p = self.data.get(f"predictions:{s}")
            if not p:
                out.append(f"**ML forecast:** no models are trained for {s} yet. Open **Predictions** and click *Train* (takes ~10–60 s).")
            else:
                rows = ["| Horizon | Best model | Forecast | 95% interval |", "|---|---|---|---|"]
                for pt in p.get("forecast_path", []):
                    rows.append(f"| {pt['horizon']} | {pt['model'].replace('_', ' ')} | {_fmt_money(pt['predicted'], cur)} | "
                                f"{_fmt_money(pt['lower'], cur)} – {_fmt_money(pt['upper'], cur)} |")
                out.append("**ML forecast** (from current price " + _fmt_money(p.get("current_price"), cur) + ")\n" + "\n".join(rows) +
                           "\n\n*Intervals are wide because short-term returns are close to a random walk — treat forecasts as uncertain estimates.*")
        return "\n\n".join(out)

    def _compare(self) -> str:
        rows = ["| Metric | " + " | ".join(self.symbols) + " |", "|---|" + "---|" * len(self.symbols)]

        def row(label, fn):
            vals = []
            for s in self.symbols:
                d = self.data.get(f"stock:{s}") or {}
                try:
                    vals.append(fn(d, d.get("metrics") or {}, self.data.get(f"technicals:{s}") or {}))
                except Exception:
                    vals.append("n/a")
            rows.append(f"| {label} | " + " | ".join(vals) + " |")

        row("Price", lambda d, m, t: _fmt_money(d.get("current_price"), d.get("currency", "USD")))
        row("Change today", lambda d, m, t: _pct(d.get("change_pct"), True))
        row("Market cap", lambda d, m, t: _fmt_big(m.get("market_cap")))
        row("P/E", lambda d, m, t: f"{m['pe_ratio']:.1f}" if m.get("pe_ratio") else "n/a")
        row("Beta", lambda d, m, t: f"{m['beta']:.2f}" if m.get("beta") is not None else "n/a")
        row("Profit margin", lambda d, m, t: _pct(m.get("profit_margin")))
        row("RSI (14)", lambda d, m, t: f"{t['rsi_14']:.1f}" if t.get("rsi_14") is not None else "n/a")
        row("Technical signal", lambda d, m, t: t.get("overall_signal", "n/a"))
        notes = []
        pes = {s: (self.data.get(f"stock:{s}") or {}).get("metrics", {}).get("pe_ratio") for s in self.symbols}
        pes = {k: v for k, v in pes.items() if v}
        if len(pes) >= 2:
            lo, hi = min(pes, key=pes.get), max(pes, key=pes.get)
            notes.append(f"- **{hi}** trades at the highest earnings multiple (P/E {pes[hi]:.1f}) and **{lo}** at the lowest ({pes[lo]:.1f}).")
        betas = {s: (self.data.get(f"stock:{s}") or {}).get("metrics", {}).get("beta") for s in self.symbols}
        betas = {k: v for k, v in betas.items() if v is not None}
        if len(betas) >= 2:
            notes.append(f"- **{max(betas, key=betas.get)}** has the highest beta, i.e. the largest expected swings relative to the market.")
        return "### Comparison: " + " vs ".join(self.symbols) + "\n" + "\n".join(rows) + ("\n\n**Interpretation**\n" + "\n".join(notes) if notes else "")

    def _portfolio(self) -> str:
        p = self.data.get("portfolio")
        if not p:
            return "### Your portfolio\nI couldn't load your portfolio."
        if p.get("empty"):
            return "### Your portfolio\nYou don't have a portfolio yet — create one on the **Portfolio** page and record a few transactions."
        lines = [f"### Your portfolio: {p.get('name')}",
                 f"**Value:** {_fmt_money(p['current_value'])} · invested {_fmt_money(p['total_invested'])} · "
                 f"unrealized return **{_pct(p['return_pct'], True)}** ({_fmt_money(p['absolute_return'])})"]
        risk = []
        if p.get("portfolio_volatility") is not None:
            risk.append(f"- Annualized volatility: {p['portfolio_volatility']}%")
        if p.get("sharpe_ratio") is not None:
            sr = p["sharpe_ratio"]
            risk.append(f"- Sharpe ratio: {sr:.2f} ({'strong' if sr > 1 else 'moderate' if sr > 0.5 else 'weak'} risk-adjusted return)")
        if p.get("max_drawdown") is not None:
            risk.append(f"- Max drawdown (1y): {p['max_drawdown']}%")
        if p.get("beta") is not None:
            risk.append(f"- Beta vs S&P 500: {p['beta']}")
        if p.get("var_95") is not None:
            risk.append(f"- 1-day 95% VaR: {_fmt_money(p['var_95'])} (expected shortfall {_fmt_money(p.get('cvar_95'))})")
        if risk:
            lines.append("**Risk metrics**\n" + "\n".join(risk))
        warnings = []
        for h in p.get("holdings", []):
            if (h.get("weight") or 0) > 30:
                warnings.append(f"- **{h['symbol']}** is {h['weight']:.0f}% of the portfolio — a concentrated position.")
        for sector, w in (p.get("sector_allocation") or {}).items():
            if w > 50:
                warnings.append(f"- **{sector}** makes up {w:.0f}% — consider sector diversification.")
        if len(p.get("holdings", [])) < 5:
            warnings.append(f"- Only {len(p.get('holdings', []))} holdings — more positions usually reduce stock-specific risk.")
        if warnings:
            lines.append("**Diversification check**\n" + "\n".join(warnings))
        return "\n\n".join(lines)

    def _market(self) -> str:
        m = self.data.get("market") or {}
        idx = "\n".join(f"- {i['name']}: {i['value']:,.2f} ({'+' if i['change_pct'] >= 0 else ''}{i['change_pct']}%)" for i in m.get("indices", []))
        g = ", ".join(f"{x['symbol']} (+{x['change_pct']}%)" for x in m.get("top_gainers", [])[:3]) or "n/a"
        lo = ", ".join(f"{x['symbol']} ({x['change_pct']}%)" for x in m.get("top_losers", [])[:3]) or "n/a"
        return f"### Market overview (US market {m.get('market_status', 'n/a')})\n{idx}\n\n**Top gainers:** {g}\n**Top losers:** {lo}"

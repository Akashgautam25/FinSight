"""
FinSight AI — Research Report Service
Builds a structured equity research report from live (or simulated) data and
exports it to PDF with ReportLab (including a native vector price chart).
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

import numpy as np
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent import FinSightAgent
from app.config import settings
from app.data import market_data as md
from app.models import ResearchReport
from app.schemas.ai import GenerateReportRequest
from app.services.news_service import NewsService
from app.services.prediction_service import PredictionService
from app.services.stock_service import StockService

logger = logging.getLogger("finsight.reports")


def _risk_profile(symbol: str) -> dict:
    """1-year realised risk statistics vs the S&P 500 (synchronous)."""
    try:
        closes, _ = md.closes([symbol, "^GSPC"], "1y")
    except md.MarketDataError:
        return {}
    if symbol not in closes.columns:
        return {}
    r = closes[symbol].pct_change().dropna()
    if len(r) < 30:
        return {}
    cum = (1 + r).cumprod()
    out = {
        "return_1y_pct": round(float((cum.iloc[-1] - 1) * 100), 2),
        "volatility_pct": round(float(r.std() * np.sqrt(252) * 100), 2),
        "max_drawdown_pct": round(float((cum / cum.cummax() - 1).min() * 100), 2),
        "var_95_pct": round(float(-np.percentile(r, 5) * 100), 2),
        "sharpe_ratio": round(float((r.mean() * 252 - 0.05) / (r.std() * np.sqrt(252))), 2) if r.std() > 0 else None,
    }
    if "^GSPC" in closes.columns:
        m = closes["^GSPC"].pct_change().reindex(r.index).fillna(0)
        if m.var() > 0:
            out["beta_1y"] = round(float(np.cov(r, m)[0, 1] / m.var()), 2)
    return out


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, payload: GenerateReportRequest, user_id: str) -> dict:
        symbol = payload.symbol.strip().upper()
        stocks = StockService()
        detail = await stocks.get_stock_detail(symbol)
        if not detail:
            raise HTTPException(status_code=404, detail=f"No market data found for {symbol}")

        history, technicals, risk = await asyncio.gather(
            stocks.get_history(symbol, "1y", "1d"),
            self._safe(stocks.get_technical_indicators(symbol)),
            asyncio.to_thread(_risk_profile, symbol),
        )
        sentiment, news, predictions = None, None, None
        if payload.include_sentiment:
            news_svc = NewsService()
            sentiment = await news_svc.get_sentiment_summary(symbol, days=30)
            news = await news_svc.get_stock_news(symbol, limit=6, days=30)
        if payload.include_predictions:
            predictions = await PredictionService().get_predictions(symbol)

        d = detail.model_dump(mode="json")
        t = technicals.model_dump(mode="json") if technicals else None
        m = d.get("metrics") or {}
        report_id = str(uuid.uuid4())
        title = payload.report_title or f"Equity Research Report: {detail.name} ({symbol})"

        # Executive summary: LLM if configured, otherwise the offline analyst
        data_bundle = {f"stock:{symbol}": d}
        if t:
            data_bundle[f"technicals:{symbol}"] = t
        if sentiment:
            data_bundle[f"sentiment:{symbol}"] = {**sentiment, "headlines": [
                {"title": a["title"], "sentiment": a.get("sentiment"), "source": a.get("source")} for a in (news or {}).get("articles", [])[:3]]}
        if predictions:
            data_bundle[f"predictions:{symbol}"] = predictions
        summary, provider = await self._summary(symbol, data_bundle)

        cur = detail.currency
        risk_text = []
        if risk:
            risk_text.append(
                f"Over the past year {symbol} returned {risk.get('return_1y_pct')}% with annualized volatility of "
                f"{risk.get('volatility_pct')}% and a maximum drawdown of {risk.get('max_drawdown_pct')}%."
            )
            if risk.get("beta_1y") is not None:
                risk_text.append(f"Its realised beta versus the S&P 500 was {risk['beta_1y']}, "
                                 f"{'amplifying' if risk['beta_1y'] > 1 else 'dampening'} broad market moves.")
            risk_text.append(f"On a typical bad day (5th percentile) the stock fell about {risk.get('var_95_pct')}% (1-day historical VaR).")
        if m.get("debt_to_equity") is not None:
            risk_text.append(f"Debt-to-equity is {m['debt_to_equity']}, which indicates its balance-sheet leverage.")
        risk_text.append("Key external risks include interest-rate changes, sector-specific competition and macroeconomic shocks.")

        closes = [p["close"] for p in history.get("data", []) if p.get("close") is not None]
        report_data = {
            "symbol": symbol,
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "company": {"name": detail.name, "sector": detail.sector, "industry": detail.industry,
                        "exchange": detail.exchange, "currency": cur, "description": detail.description},
            "stock_detail": d,
            "technicals": t,
            "risk_metrics": risk,
            "sentiment": sentiment,
            "recent_news": [{k: a.get(k) for k in ("title", "url", "source", "published_at", "sentiment", "compound_score")}
                            for a in (news or {}).get("articles", [])[:6]],
            "predictions": {"forecast_path": predictions.get("forecast_path"), "best_model_by_horizon": predictions.get("best_model_by_horizon"),
                            "trained_at": predictions.get("trained_at")} if predictions else None,
            "price_series": {"dates": [p["date"] for p in history.get("data", [])][::3], "closes": closes[::3]},
            "executive_summary": summary,
            "summary_provider": provider,
            "risk_assessment": " ".join(risk_text),
            "is_demo": detail.is_demo,
            "disclaimer": (
                "This report was generated automatically by FinSight AI for educational and research purposes only. "
                "Forecasts are statistical estimates with substantial uncertainty, not guarantees. "
                "Nothing in this report is personalised investment advice."
            ),
        }

        os.makedirs(settings.reports_storage_path, exist_ok=True)
        pdf_path = os.path.join(settings.reports_storage_path, f"report_{symbol.replace('^', '')}_{report_id[:8]}.pdf")
        await asyncio.to_thread(self._build_pdf, pdf_path, report_data)

        record = ResearchReport(
            id=report_id, user_id=user_id, symbol=symbol, title=title, status="ready",
            report_data=report_data, pdf_path=pdf_path,
            share_token=uuid.uuid4().hex[:24], is_public=False,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return {
            "id": report_id, "title": title, "symbol": symbol, "status": "ready", "pdf_available": True,
            "generated_at": record.generated_at.isoformat() if record.generated_at else report_data["generated_at"],
            "report_data": report_data,
        }

    @staticmethod
    async def _safe(coro):
        try:
            return await coro
        except Exception:
            return None

    async def _summary(self, symbol: str, data: dict):
        from app.ai import llm

        prompt = (f"VERIFIED DATA:\n{FinSightAgent._context(data)}\n\nWrite a 150-word executive summary for an equity research "
                  f"report on {symbol}: business, valuation, technical picture, sentiment and key risks. Plain prose, no headings, "
                  "no buy/sell recommendation, use only the numbers above.")
        text, provider = await llm.complete([
            {"role": "system", "content": "You are an equity research analyst writing for students. Never invent numbers."},
            {"role": "user", "content": prompt},
        ], max_tokens=350)
        if text:
            return text.replace("⚠️ Educational information only — not financial advice.", "").strip(), provider
        return self._template_summary(symbol, data), "template"

    @staticmethod
    def _template_summary(symbol: str, data: dict) -> str:
        d = data.get(f"stock:{symbol}") or {}
        m = d.get("metrics") or {}
        t = data.get(f"technicals:{symbol}") or {}
        s = data.get(f"sentiment:{symbol}") or {}
        cur = d.get("currency", "USD")
        parts = [f"{d.get('name', symbol)} ({symbol}) operates in the {d.get('sector') or 'n/a'} sector"
                 f"{' (' + d['industry'] + ')' if d.get('industry') else ''} and last traded at {d.get('current_price')} {cur}."]
        if m.get("pe_ratio"):
            pe = m["pe_ratio"]
            parts.append(f"At a trailing P/E of {pe:.1f}, the market prices the stock at "
                         f"{'a premium, implying high growth expectations' if pe > 30 else 'a moderate multiple' if pe > 15 else 'a modest multiple'}.")
        if m.get("market_cap"):
            parts.append(f"Market capitalisation is approximately {m['market_cap'] / 1e9:,.1f} billion {cur}.")
        if t:
            rsi = t.get("rsi_14")
            parts.append(f"The technical picture is {t.get('overall_signal', 'neutral')}: RSI(14) stands at "
                         f"{(f'{rsi:.1f}' if rsi is not None else 'n/a')} and {len([x for x in t.get('signals', []) if x['signal'] == 'bullish'])} of "
                         f"{len(t.get('signals', []))} indicators are bullish.")
        if s.get("news_count"):
            parts.append(f"News sentiment over the last {s.get('period_days')} days is {s.get('overall_sentiment')} "
                         f"({s.get('positive_pct')}% positive vs {s.get('negative_pct')}% negative across {s.get('news_count')} articles).")
        return " ".join(parts)

    # ── PDF ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_pdf(path: str, data: dict) -> None:
        from reportlab.graphics.charts.lineplots import LinePlot
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape

        def P(text, style):
            return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                                title=data["title"], author="FinSight AI")
        ss = getSampleStyleSheet()
        title_s = ParagraphStyle("t", parent=ss["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), spaceAfter=4)
        h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, leading=16, textColor=colors.HexColor("#1d4ed8"), spaceBefore=10, spaceAfter=5)
        body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13.5, textColor=colors.HexColor("#334155"))
        small = ParagraphStyle("s", parent=body, fontSize=7.8, leading=10.5, textColor=colors.HexColor("#64748b"))
        flow = []

        d = data.get("stock_detail") or {}
        m = d.get("metrics") or {}
        cur = d.get("currency", "USD")
        flow.append(P(data["title"], title_s))
        meta_line = f"{d.get('exchange') or ''} · {d.get('sector') or ''} · Generated {data['generated_at'][:16].replace('T', ' ')} UTC"
        if data.get("is_demo"):
            meta_line += " · SIMULATED DEMO DATA"
        flow.append(P(meta_line, small))
        flow.append(Spacer(1, 8))

        flow.append(P("1. Executive Summary", h2))
        flow.append(P(data["executive_summary"], body))

        def fmt(v, kind="num"):
            if v is None:
                return "—"
            if kind == "pct":
                return f"{v * 100:.2f}%"
            if kind == "big":
                return f"{v / 1e12:.2f}T" if abs(v) >= 1e12 else f"{v / 1e9:.2f}B" if abs(v) >= 1e9 else f"{v / 1e6:.1f}M"
            return f"{v:,.2f}"

        flow.append(P("2. Valuation & Fundamentals", h2))
        rows = [
            ["Current price", f"{fmt(d.get('current_price'))} {cur}", "Market cap", fmt(m.get("market_cap"), "big")],
            ["P/E (trailing)", fmt(m.get("pe_ratio")), "EPS (trailing)", fmt(m.get("eps"))],
            ["Beta", fmt(m.get("beta")), "Dividend yield", fmt(m.get("dividend_yield"), "pct")],
            ["Profit margin", fmt(m.get("profit_margin"), "pct"), "Return on equity", fmt(m.get("roe"), "pct")],
            ["Debt / equity", fmt(m.get("debt_to_equity")), "Revenue growth", fmt(m.get("revenue_growth"), "pct")],
            ["52-week high", fmt(m.get("week_52_high")), "52-week low", fmt(m.get("week_52_low"))],
        ]
        table = Table(rows, colWidths=[38 * mm, 44 * mm, 38 * mm, 44 * mm])
        table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.8),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(table)

        closes = (data.get("price_series") or {}).get("closes") or []
        if len(closes) > 5:
            flow.append(P("3. Price History (1 year)", h2))
            drawing = Drawing(170 * mm, 55 * mm)
            lp = LinePlot()
            lp.x, lp.y, lp.width, lp.height = 12 * mm, 8 * mm, 152 * mm, 42 * mm
            lp.data = [list(enumerate(closes))]
            lp.lines[0].strokeColor = colors.HexColor("#2563eb")
            lp.lines[0].strokeWidth = 1.4
            lp.xValueAxis.visible = False
            lo, hi = min(closes), max(closes)
            pad = (hi - lo) * 0.08 or 1
            lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = lo - pad, hi + pad
            lp.yValueAxis.labels.fontSize = 7
            lp.yValueAxis.labelTextFormat = "%0.0f"
            drawing.add(lp)
            dates = (data.get("price_series") or {}).get("dates") or []
            if dates:
                drawing.add(String(12 * mm, 1 * mm, dates[0], fontSize=7, fillColor=colors.HexColor("#64748b")))
                drawing.add(String(150 * mm, 1 * mm, dates[-1], fontSize=7, fillColor=colors.HexColor("#64748b")))
            flow.append(drawing)

        t = data.get("technicals")
        if t:
            flow.append(P("4. Technical Analysis", h2))
            def r(v, n=2):
                return f"{v:,.{n}f}" if isinstance(v, (int, float)) else "—"
            flow.append(P(f"Overall signal: {t.get('overall_signal', 'neutral').upper()} · RSI(14) {r(t.get('rsi_14'), 1)} · "
                          f"MACD {r(t.get('macd'))} vs signal {r(t.get('macd_signal'))} · SMA50 {r(t.get('sma_50'))} · "
                          f"SMA200 {r(t.get('sma_200'))}", body))
            for s in t.get("signals", []):
                flow.append(P(f"• {s['indicator']}: {s['signal']} — {s['detail']}", body))

        s = data.get("sentiment")
        if s:
            flow.append(P("5. News Sentiment", h2))
            flow.append(P(f"Overall: {s.get('overall_sentiment', 'neutral').upper()} · {s.get('positive_pct')}% positive · "
                          f"{s.get('negative_pct')}% negative · {s.get('neutral_pct')}% neutral · {s.get('news_count')} articles "
                          f"(model: {s.get('sentiment_model')})", body))
            for a in data.get("recent_news", [])[:5]:
                flow.append(P(f"• [{a.get('sentiment')}] {a.get('title')} — {a.get('source') or ''}", body))

        p = data.get("predictions")
        if p and p.get("forecast_path"):
            flow.append(P("6. Machine-Learning Forecasts", h2))
            prow = [["Horizon", "Best model", "Forecast", "95% interval"]]
            for pt in p["forecast_path"]:
                prow.append([pt["horizon"], pt["model"].replace("_", " ").title(), f"{pt['predicted']:,.2f}", f"{pt['lower']:,.2f} – {pt['upper']:,.2f}"])
            pt_table = Table(prow, colWidths=[25 * mm, 45 * mm, 35 * mm, 55 * mm])
            pt_table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8.8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ]))
            flow.append(pt_table)
            flow.append(P("Forecasts are model estimates; intervals reflect validation-set error and are typically wide.", small))

        flow.append(P("7. Risk Assessment", h2))
        flow.append(P(data["risk_assessment"], body))
        flow.append(Spacer(1, 10))
        flow.append(P("Disclaimer", h2))
        flow.append(P(data["disclaimer"], small))
        doc.build(flow)

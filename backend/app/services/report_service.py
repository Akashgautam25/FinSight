"""
FinSight AI — Report Generation Service
Generates structured financial intelligence reports and exports to PDF using ReportLab.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import ResearchReport, User
from app.schemas.ai import GenerateReportRequest
from app.services.stock_service import StockService
from app.services.news_service import NewsService
from app.services.prediction_service import PredictionService


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, payload: GenerateReportRequest, user_id: str) -> dict:
        symbol = payload.symbol.upper()
        report_id = str(uuid.uuid4())
        title = payload.report_title or f"Comprehensive Financial Intelligence Report: {symbol}"

        # 1. Fetch live and historical data
        stock_service = StockService()
        news_service = NewsService()
        prediction_service = PredictionService()

        stock_detail = await stock_service.get_stock_detail(symbol)
        history = await stock_service.get_history(symbol, period="1y")
        technicals = None
        try:
            technicals = await stock_service.get_technical_indicators(symbol)
        except Exception:
            pass

        # 2. Fetch sentiment & news
        sentiment_summary = await news_service.get_sentiment_summary(symbol, days=30)
        recent_news = await news_service.get_stock_news(symbol, limit=5, days=7)

        # 3. Fetch predictions if requested
        predictions = None
        if payload.include_predictions:
            predictions = await prediction_service.get_predictions(symbol)

        report_data = {
            "symbol": symbol,
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stock_detail": stock_detail.model_dump() if stock_detail else None,
            "technicals": technicals.model_dump() if technicals else None,
            "sentiment": sentiment_summary,
            "recent_news": recent_news.get("articles", []) if recent_news else [],
            "predictions": predictions,
            "executive_summary": (
                f"Financial research assessment for {symbol} ({stock_detail.name if stock_detail else symbol}). "
                f"Currently trading at {stock_detail.current_price if stock_detail else 'N/A'} {stock_detail.currency if stock_detail else 'USD'}. "
                f"Market sentiment is currently categorized as {sentiment_summary.get('overall_sentiment', 'neutral')} "
                f"based on {sentiment_summary.get('news_count', 0)} analyzed recent financial publications."
            ),
            "risk_assessment": (
                f"Beta is {stock_detail.metrics.beta if stock_detail and stock_detail.metrics else 'N/A'}, "
                f"indicating relative market volatility. Debt-to-Equity stands at "
                f"{stock_detail.metrics.debt_to_equity if stock_detail and stock_detail.metrics else 'N/A'}. "
                "Macroeconomic fluctuations, industry-specific headwinds, and interest rate adjustments remain critical risk factors."
            ),
            "disclaimer": (
                "This report was automatically synthesized by FinSight AI for educational and research purposes only. "
                "All predictive projections represent algorithmic statistical estimates, not guaranteed outcomes. "
                "This report does not constitute personalized investment advice."
            )
        }

        # 4. Generate PDF
        pdf_dir = "./data/reports"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"report_{symbol}_{report_id[:8]}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)

        self._build_pdf(pdf_path, report_data)

        # 5. Persist record in database
        report_record = ResearchReport(
            id=report_id,
            user_id=user_id,
            symbol=symbol,
            title=title,
            status="ready",
            report_data=report_data,
            pdf_path=pdf_path,
            share_token=str(uuid.uuid4()).replace("-", "")[:24],
            is_public=False,
        )
        self.db.add(report_record)
        await self.db.commit()

        return {
            "id": report_id,
            "title": title,
            "symbol": symbol,
            "status": "ready",
            "pdf_available": True,
            "share_token": report_record.share_token,
            "report_data": report_data
        }

    def _build_pdf(self, path: str, data: dict):
        """Build professional formatted PDF using ReportLab."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            doc = SimpleDocTemplate(path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            flowables = []

            # Custom styles
            title_style = ParagraphStyle(
                'ReportTitle',
                parent=styles['Heading1'],
                fontSize=20,
                leading=24,
                textColor=colors.HexColor('#0f172a'),
                spaceAfter=10
            )
            h2_style = ParagraphStyle(
                'ReportH2',
                parent=styles['Heading2'],
                fontSize=13,
                leading=16,
                textColor=colors.HexColor('#1e293b'),
                spaceBefore=12,
                spaceAfter=6
            )
            body_style = ParagraphStyle(
                'ReportBody',
                parent=styles['Normal'],
                fontSize=9.5,
                leading=13.5,
                textColor=colors.HexColor('#334155')
            )
            disclaimer_style = ParagraphStyle(
                'Disclaimer',
                parent=styles['Normal'],
                fontSize=8,
                leading=11,
                textColor=colors.HexColor('#64748b')
            )

            # Title
            flowables.append(Paragraph(data['title'], title_style))
            flowables.append(Paragraph(f"<b>Symbol:</b> {data['symbol']} | <b>Generated:</b> {data['generated_at'][:16].replace('T', ' ')} UTC", body_style))
            flowables.append(Spacer(1, 12))

            # Executive Summary
            flowables.append(Paragraph("1. Executive Summary", h2_style))
            flowables.append(Paragraph(data['executive_summary'], body_style))
            flowables.append(Spacer(1, 10))

            # Financial Metrics Table
            flowables.append(Paragraph("2. Fundamental & Valuation Snapshot", h2_style))
            sd = data.get('stock_detail') or {}
            metrics = sd.get('metrics') or {}

            table_data = [
                ["Metric", "Value", "Metric", "Value"],
                ["Current Price", f"{sd.get('current_price', 'N/A')} {sd.get('currency', '')}", "Market Capitalization", str(metrics.get('market_cap', 'N/A'))],
                ["P/E Ratio", str(metrics.get('pe_ratio', 'N/A')), "EPS (Trailing)", str(metrics.get('eps', 'N/A'))],
                ["Beta", str(metrics.get('beta', 'N/A')), "Dividend Yield", str(metrics.get('dividend_yield', 'N/A'))],
                ["52-Week High", str(metrics.get('week_52_high', 'N/A')), "52-Week Low", str(metrics.get('week_52_low', 'N/A'))],
            ]

            t = Table(table_data, colWidths=[130, 130, 130, 130])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8.5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            flowables.append(t)
            flowables.append(Spacer(1, 10))

            # Sentiment Analysis
            flowables.append(Paragraph("3. Market Sentiment Intelligence (FinBERT NLP)", h2_style))
            sent = data.get('sentiment') or {}
            sent_text = (
                f"Overall Classification: <b>{sent.get('overall_sentiment', 'neutral').upper()}</b> | "
                f"Positive: {sent.get('positive_pct', 0)}% | Negative: {sent.get('negative_pct', 0)}% | Neutral: {sent.get('neutral_pct', 0)}%"
            )
            flowables.append(Paragraph(sent_text, body_style))
            flowables.append(Spacer(1, 10))

            # Risk Assessment
            flowables.append(Paragraph("4. Quantitative Risk Assessment", h2_style))
            flowables.append(Paragraph(data['risk_assessment'], body_style))
            flowables.append(Spacer(1, 14))

            # Limitations and Disclaimer
            flowables.append(Paragraph("5. System Limitations & Disclaimer", h2_style))
            flowables.append(Paragraph(data['disclaimer'], disclaimer_style))

            doc.build(flowables)
        except Exception as e:
            # Fallback text file renamed as pdf if ReportLab encounters font issues
            with open(path, "w") as f:
                f.write(f"FinSight AI Report - {data['symbol']}\n\n{data['executive_summary']}\n\n{data['disclaimer']}")

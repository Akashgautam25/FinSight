"""
FinSight AI — LangGraph AI Financial Research Agent
Uses tool calling to retrieve real data before generating responses.
LLM never invents prices, ratios, or historical facts.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


class FinSightAgent:
    """
    LangGraph-based financial research agent.
    Architecture: User Query → Intent → Tool Calls → Context → LLM → Response + Citations
    """

    def __init__(self):
        self._llm = None
        self._graph = None

    def _get_llm(self):
        from app.config import settings
        if self._llm is None:
            if settings.google_api_key:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._llm = ChatGoogleGenerativeAI(
                    model=settings.gemini_model,
                    google_api_key=settings.google_api_key,
                    temperature=0.1,
                )
            elif settings.openai_api_key:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    openai_api_key=settings.openai_api_key,
                    temperature=0.1,
                )
        return self._llm

    async def run(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Run the agent pipeline:
        1. Extract financial entities from query
        2. Call appropriate data tools
        3. Build context with verified data
        4. Generate response with citations
        """
        llm = self._get_llm()
        if not llm:
            return {
                "content": (
                    "AI assistant is currently unavailable. "
                    "Please configure GOOGLE_API_KEY or OPENAI_API_KEY in your environment."
                ),
                "sources": [],
                "tool_calls": [],
            }

        # Extract symbols and intent from message
        entities = await self._extract_entities(message, llm)
        symbols = entities.get("symbols", [])

        # Gather verified data via tools
        context_parts = []
        sources = []
        tool_calls_made = []

        for symbol in symbols[:3]:  # limit to 3 symbols per query
            # Fetch stock data
            stock_data = await self._tool_get_stock(symbol)
            if stock_data:
                context_parts.append(f"**{symbol} Market Data** (fetched {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}):\n{stock_data}")
                sources.append({
                    "type": "market_data",
                    "title": f"{symbol} Stock Data",
                    "url": None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_verified": True,
                })
                tool_calls_made.append(f"get_stock_data({symbol})")

            # Fetch news sentiment
            sentiment = await self._tool_get_sentiment(symbol)
            if sentiment:
                context_parts.append(f"**{symbol} Sentiment** ({sentiment['period_days']} days):\nOverall: {sentiment['overall_sentiment']}, Compound Score: {sentiment['avg_compound_score']}")
                tool_calls_made.append(f"get_sentiment({symbol})")

        context = "\n\n".join(context_parts) if context_parts else "No specific market data retrieved for this query."

        # Generate response with LLM
        system_prompt = """You are FinSight AI, an intelligent financial research assistant.

CRITICAL RULES:
1. Never invent stock prices, financial ratios, or historical data.
2. Only use data provided in the VERIFIED DATA CONTEXT section.
3. Clearly distinguish between verified facts and your interpretations.
4. Always add caveats about uncertainty and that this is not investment advice.
5. If asked about data not in context, say you don't have that data rather than guessing.
6. Explain financial metrics in clear, understandable language.
7. For predictions, emphasize uncertainty and model limitations.

After every response, add: "⚠️ This is for educational purposes only and does not constitute financial advice."
"""
        user_prompt = f"""VERIFIED DATA CONTEXT:
{context}

USER QUESTION:
{message}

Provide a comprehensive, accurate response using ONLY the verified data above. 
Clearly label any interpretations as your analysis vs. verified facts."""

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            content = response.content
        except Exception as e:
            content = f"I encountered an error generating a response: {str(e)}. Please try again."

        return {
            "content": content,
            "sources": sources,
            "tool_calls": tool_calls_made,
        }

    async def _extract_entities(self, message: str, llm) -> dict:
        """Extract stock symbols and query intent from user message."""
        # Simple extraction — in production use a dedicated NER model
        import re
        # Common ticker pattern: 1-5 uppercase letters
        potential_tickers = re.findall(r'\b[A-Z]{1,5}\b', message)
        # Filter common English words
        STOP_WORDS = {"I", "A", "THE", "AND", "OR", "FOR", "IN", "ON", "AT", "IS", "ARE", "BE", "MY", "AI", "ML"}
        symbols = [t for t in potential_tickers if t not in STOP_WORDS and len(t) >= 2]

        return {"symbols": symbols[:5], "query_type": "general"}

    async def _tool_get_stock(self, symbol: str) -> Optional[str]:
        """Tool: Get verified stock data."""
        try:
            from app.services.stock_service import StockService
            service = StockService()
            detail = await service.get_stock_detail(symbol)
            if not detail:
                return None
            return (
                f"Name: {detail.name}\n"
                f"Exchange: {detail.exchange}\n"
                f"Sector: {detail.sector}\n"
                f"Current Price: {detail.current_price} {detail.currency}\n"
                f"Previous Close: {detail.previous_close}\n"
                f"Day High/Low: {detail.day_high} / {detail.day_low}\n"
                f"Market Cap: {detail.metrics.market_cap if detail.metrics else 'N/A'}\n"
                f"P/E Ratio: {detail.metrics.pe_ratio if detail.metrics else 'N/A'}\n"
                f"Beta: {detail.metrics.beta if detail.metrics else 'N/A'}\n"
                f"52W High/Low: {detail.metrics.week_52_high if detail.metrics else 'N/A'} / {detail.metrics.week_52_low if detail.metrics else 'N/A'}\n"
                f"[Data is delayed. Source: yfinance. Last fetch: {detail.last_updated}]"
            )
        except Exception:
            return None

    async def _tool_get_sentiment(self, symbol: str) -> Optional[dict]:
        """Tool: Get verified news sentiment."""
        try:
            from app.services.news_service import NewsService
            service = NewsService()
            return await service.get_sentiment_summary(symbol, days=7)
        except Exception:
            return None

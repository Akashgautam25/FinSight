"""
FinSight AI — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import create_tables
from app.routers import (
    auth,
    stocks,
    news,
    portfolio,
    predictions,
    optimization,
    ai_assistant,
    reports,
    alerts,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    await create_tables()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Financial Intelligence & Stock Research Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Authentication"])
app.include_router(stocks.router, prefix=f"{API_PREFIX}/stocks", tags=["Stocks"])
app.include_router(news.router, prefix=f"{API_PREFIX}/news", tags=["News & Sentiment"])
app.include_router(portfolio.router, prefix=f"{API_PREFIX}/portfolios", tags=["Portfolio"])
app.include_router(predictions.router, prefix=f"{API_PREFIX}/predictions", tags=["ML Predictions"])
app.include_router(optimization.router, prefix=f"{API_PREFIX}/optimization", tags=["Optimization"])
app.include_router(ai_assistant.router, prefix=f"{API_PREFIX}/ai", tags=["AI Assistant"])
app.include_router(reports.router, prefix=f"{API_PREFIX}/reports", tags=["Reports"])
app.include_router(alerts.router, prefix=f"{API_PREFIX}/alerts", tags=["Alerts"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "environment": settings.environment}

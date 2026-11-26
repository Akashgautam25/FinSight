"""
FinSight AI — FastAPI Application Entry Point
Run:  uvicorn app.main:app --reload      (from the backend/ directory)
Docs: http://localhost:8000/docs
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import app.ml.models  # noqa: F401,I001 — must load XGBoost before PyTorch (OpenMP conflict on macOS)
from app.config import settings
from app.database import create_tables
from app.routers import (
    ai_assistant,
    alerts,
    auth,
    news,
    notifications,
    optimization,
    portfolio,
    predictions,
    reports,
    stocks,
    watchlists,
)

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
for noisy in ("yfinance", "urllib3", "peewee", "httpx", "httpx2", "curl_cffi", "huggingface_hub", "transformers", "filelock"):
    logging.getLogger(noisy).setLevel(logging.CRITICAL)
logger = logging.getLogger("finsight")


async def _warm_cache() -> None:
    """Pre-fetch the market overview so the first dashboard load is fast."""
    await asyncio.sleep(1)
    try:
        from app.services.stock_service import StockService
        await StockService().get_market_overview()
    except Exception as exc:  # warm-up is best-effort
        logger.info("Cache warm-up skipped: %s", exc)
    from app.ai.llm import warm_up
    await warm_up()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()

    from app.services.sentiment_service import start_finbert_loading
    start_finbert_loading()

    # yfinance calls run in worker threads; give the pool room for concurrent requests
    from concurrent.futures import ThreadPoolExecutor
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=32, thread_name_prefix="finsight-io"))

    background = [asyncio.create_task(_warm_cache())]
    if settings.alert_check_interval_seconds > 0:
        from app.services.alert_service import alert_loop
        background.append(asyncio.create_task(alert_loop(settings.alert_check_interval_seconds)))

    from app.ai.llm import status as llm_status
    ai = await llm_status()
    logger.info("FinSight AI started · db=%s · market data=%s · AI=%s",
                "sqlite" if settings.is_sqlite else "postgresql", settings.market_data_mode,
                ai["active"] or "offline analyst (start Ollama or add GOOGLE_API_KEY)")
    yield
    for task in background:
        task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Financial Intelligence & Stock Research Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Check the backend logs for details."})


API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Authentication"])
app.include_router(stocks.router, prefix=f"{API_PREFIX}/stocks", tags=["Stocks"])
app.include_router(news.router, prefix=f"{API_PREFIX}/news", tags=["News & Sentiment"])
app.include_router(portfolio.router, prefix=f"{API_PREFIX}/portfolios", tags=["Portfolio"])
app.include_router(watchlists.router, prefix=f"{API_PREFIX}/watchlists", tags=["Watchlists"])
app.include_router(predictions.router, prefix=f"{API_PREFIX}/predictions", tags=["ML Predictions"])
app.include_router(optimization.router, prefix=f"{API_PREFIX}/optimization", tags=["Optimization"])
app.include_router(ai_assistant.router, prefix=f"{API_PREFIX}/ai", tags=["AI Assistant"])
app.include_router(reports.router, prefix=f"{API_PREFIX}/reports", tags=["Reports"])
app.include_router(alerts.router, prefix=f"{API_PREFIX}/alerts", tags=["Alerts"])
app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications", tags=["Notifications"])


@app.get("/", tags=["Health"])
async def root():
    return {"app": settings.app_name, "version": settings.app_version, "status": "operational", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "environment": settings.environment}


class ClientError(BaseModel):
    context: str = Field("", max_length=100)
    message: str = Field("", max_length=1000)
    stack: str = Field("", max_length=8000)
    url: str = Field("", max_length=500)
    build: str = Field("", max_length=50)
    user_agent: str = Field("", max_length=300)


@app.post(f"{API_PREFIX}/system/client-errors", status_code=204, tags=["Health"])
async def client_error(report: ClientError):
    """Browser-side errors are reported here and written to the backend log for diagnosis."""
    logging.getLogger("finsight.client").warning(
        "CLIENT ERROR [%s] %s\n  url=%s build=%s ua=%s\n%s",
        report.context, report.message, report.url, report.build, report.user_agent[:120], report.stack,
    )


async def _llm_status() -> dict:
    from app.ai.llm import status
    return await status()


@app.get(f"{API_PREFIX}/system/status", tags=["Health"])
async def system_status():
    """Which optional components are active (shown on the Settings page)."""
    from app.data.market_data import data_status
    from app.ml.models import model_availability
    from app.services.sentiment_service import model_status
    from app.utils import cache

    await cache.get_cache()
    return {
        "version": settings.app_version,
        "environment": settings.environment,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "cache": cache.backend_name,
        "market_data": data_status(),
        "sentiment": model_status(),
        "llm": await _llm_status(),
        "ml_models": {name: (reason or "available") for name, reason in model_availability().items()},
    }

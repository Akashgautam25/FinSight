"""
FinSight AI — Application Settings
All configuration is loaded from environment variables (or a .env file) via pydantic-settings.

Every setting has a safe development default so the backend starts with zero configuration:
  * SQLite database in ./data/finsight.db (PostgreSQL when DATABASE_URL points to it)
  * In-memory cache (Redis when REDIS_URL is reachable)
  * Live market data from Yahoo Finance with automatic fallback to simulated data
"""

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

logger = logging.getLogger("finsight.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # backend/.env takes priority over the project-root .env
        env_file=(str(PROJECT_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "FinSight AI"
    app_version: str = "1.1.0"
    environment: str = "development"
    debug: bool = False  # SQL echo + verbose logs

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'finsight.db'}"

    # ── Cache ────────────────────────────────────────────────────────────────
    # Leave empty to use the in-process memory cache.
    redis_url: str = ""

    # ── Auth ─────────────────────────────────────────────────────────────────
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 30

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Extra allowed origins as a regex, e.g. https://finsight-ai[a-z0-9-]*\.vercel\.app
    cors_origin_regex: str = ""
    frontend_url: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Market data ──────────────────────────────────────────────────────────
    # auto: live Yahoo Finance data, falling back to simulated data on failure
    # live: live data only (errors surface to the client)
    # demo: simulated data only (offline demos, tests)
    market_data_mode: str = "auto"

    # ── Optional external APIs ───────────────────────────────────────────────
    finnhub_api_key: str = ""
    news_api_key: str = ""

    # ── AI / LLM ─────────────────────────────────────────────────────────────
    # auto: first available of Gemini → Groq → OpenAI (keys) → local Ollama → offline analyst
    llm_provider: str = "auto"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_num_ctx: int = 8192
    llm_timeout_seconds: int = 60

    # ── NLP ──────────────────────────────────────────────────────────────────
    # auto: FinBERT if `transformers` is installed (loaded in background), else lexicon
    # finbert: same as auto; lexicon: never load FinBERT
    sentiment_backend: str = "auto"
    # false = never load PyTorch (no LSTM, no FinBERT) — for small cloud instances (~512 MB RAM)
    enable_torch: bool = True

    # ── Storage ──────────────────────────────────────────────────────────────
    model_storage_path: str = str(DATA_DIR / "models")
    reports_storage_path: str = str(DATA_DIR / "reports")

    # ── Background jobs ──────────────────────────────────────────────────────
    alert_check_interval_seconds: int = 300  # 0 disables the price-alert checker
    # Online demo deployments (database resets on restart)
    seed_demo_on_startup: bool = False
    pretrain_symbols: str = ""  # e.g. "AAPL,NVDA" — trained in the background after startup

    # ── Email (optional; used for password-reset links) ──────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@finsight.local"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def _resolve_secret_key(settings: Settings) -> None:
    """Use the configured key, or a persisted random key in development."""
    placeholder = not settings.secret_key or settings.secret_key.startswith("your-")
    if not placeholder:
        return
    if settings.is_production:
        raise RuntimeError("SECRET_KEY must be set in production.")

    key_file = DATA_DIR / ".secret_key"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        settings.secret_key = key_file.read_text().strip()
    else:
        settings.secret_key = secrets.token_urlsafe(64)
        key_file.write_text(settings.secret_key)
        logger.warning("SECRET_KEY not set — generated a development key in %s", key_file)


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    _resolve_secret_key(s)
    # Placeholder values copied from .env.example count as "not configured".
    for field in ("google_api_key", "groq_api_key", "openai_api_key", "finnhub_api_key", "news_api_key"):
        value = getattr(s, field)
        if value.startswith("your_") or value.startswith("your-"):
            setattr(s, field, "")
    for path in (s.model_storage_path, s.reports_storage_path):
        Path(path).mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()

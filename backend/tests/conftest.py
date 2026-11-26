"""
FinSight AI — test fixtures.

Tests run fully offline: simulated market data (MARKET_DATA_MODE=demo), a temporary
SQLite database, the lexicon sentiment model and no LLM keys.
"""

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="finsight-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/test.db",
    "MARKET_DATA_MODE": "demo",
    "MODEL_STORAGE_PATH": f"{_TMP}/models",
    "REPORTS_STORAGE_PATH": f"{_TMP}/reports",
    "ALERT_CHECK_INTERVAL_SECONDS": "0",
    "SENTIMENT_BACKEND": "lexicon",
    "GOOGLE_API_KEY": "",
    "OPENAI_API_KEY": "",
    "GROQ_API_KEY": "",
    "LLM_PROVIDER": "offline",
    "OLLAMA_BASE_URL": "http://127.0.0.1:9",
    "SECRET_KEY": "test-secret-key-for-pytest-only-0123456789",
    "REDIS_URL": "",
})

import uuid  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.database import create_tables  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "TestPass1"


@pytest.fixture(scope="session", autouse=True)
async def _database():
    await create_tables()
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(client):
    """A client logged in as a freshly registered user."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Test User"})
    assert resp.status_code == 201, resp.text
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    client.email = email
    return client

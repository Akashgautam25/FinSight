"""
FinSight AI — Backend Tests
pytest-based test suite with fixtures.
"""

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import get_db, Base

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client():
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth Tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass1",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "TestPass1",
    })
    response = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "TestPass1",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "TestPass1",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "TestPass1",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "password": "TestPass1",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrong@example.com",
        "password": "WrongPass1",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "TestPass1",
    })
    token = reg.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_protected_route_no_token(client):
    response = await client.get("/api/v1/portfolios")
    assert response.status_code == 403  # FastAPI HTTPBearer returns 403 when no credentials


# ── Financial Math Tests ──────────────────────────────────────────────────────

def test_evaluation_metrics():
    import numpy as np
    from app.ml.evaluation import evaluate_model

    y_true = np.array([100.0, 102.0, 101.0, 103.0, 104.0])
    y_pred = np.array([100.5, 101.5, 101.5, 102.5, 103.5])

    metrics = evaluate_model(y_true, y_pred, "test")

    assert metrics["mae"] is not None
    assert metrics["rmse"] is not None
    assert metrics["r_squared"] is not None
    assert metrics["mae"] > 0
    assert metrics["rmse"] >= metrics["mae"]  # RMSE >= MAE always
    assert -1 <= metrics["r_squared"] <= 1
    assert metrics["n_samples"] == 5


def test_evaluation_perfect_prediction():
    import numpy as np
    from app.ml.evaluation import evaluate_model

    y = np.array([100.0, 101.0, 102.0, 103.0])
    metrics = evaluate_model(y, y, "test")

    assert metrics["mae"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["mse"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["r_squared"] == pytest.approx(1.0, abs=1e-6)


def test_evaluation_handles_nan():
    import numpy as np
    from app.ml.evaluation import evaluate_model

    y_true = np.array([100.0, np.nan, 102.0])
    y_pred = np.array([100.5, 101.0, np.nan])

    metrics = evaluate_model(y_true, y_pred, "test")
    assert metrics["n_samples"] == 1  # Only one non-NaN pair


def test_feature_engineering_no_lookahead():
    """Verify that features are only computed from past data."""
    import pandas as pd
    import numpy as np
    from app.ml.feature_engineering import compute_features, create_target, time_series_split

    # Create synthetic price data
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=300, freq="D")
    df = pd.DataFrame({
        "Open": 100 + np.random.randn(300).cumsum(),
        "High": 102 + np.random.randn(300).cumsum(),
        "Low": 98 + np.random.randn(300).cumsum(),
        "Close": 100 + np.random.randn(300).cumsum(),
        "Volume": np.random.randint(1_000_000, 10_000_000, 300).astype(float),
    }, index=dates)
    df["High"] = df[["Open", "Close"]].max(axis=1) + 0.5
    df["Low"] = df[["Open", "Close"]].min(axis=1) - 0.5

    features = compute_features(df)
    X, y = create_target(features, horizon=1)
    X_train, X_val, X_test, y_train, y_val, y_test = time_series_split(X, y)

    # Train/val/test must be chronologically ordered
    assert X_train.index[-1] < X_val.index[0], "Train/val overlap detected!"
    assert X_val.index[-1] < X_test.index[0], "Val/test overlap detected!"

    # Training set should be ~70% of total
    total = len(X)
    train_pct = len(X_train) / total
    assert 0.65 <= train_pct <= 0.75, f"Unexpected train split: {train_pct}"


def test_time_series_split_no_shuffle():
    import pandas as pd
    import numpy as np
    from app.ml.feature_engineering import time_series_split

    n = 100
    idx = pd.date_range("2020-01-01", periods=n)
    X = pd.DataFrame({"a": range(n)}, index=idx)
    y = pd.Series(range(n), index=idx)

    X_train, X_val, X_test, y_train, y_val, y_test = time_series_split(X, y)

    # Verify no gaps or shuffling
    all_indices = list(X_train.index) + list(X_val.index) + list(X_test.index)
    assert all_indices == sorted(all_indices), "Time series was shuffled!"
    assert len(X_train) + len(X_val) + len(X_test) == n

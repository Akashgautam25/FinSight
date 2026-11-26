import numpy as np
import pandas as pd
import pytest

from app.data.providers.demo_provider import DemoDataProvider
from app.ml.evaluation import evaluate_model, select_best_model
from app.ml.feature_engineering import FEATURE_COLUMNS, compute_features, create_target, time_series_split


def _prices(n=400, seed=42):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n)))
    idx = pd.bdate_range("2021-01-01", periods=n)
    return pd.DataFrame({"Open": close * 0.999, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                         "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float)}, index=idx)


# ── Evaluation metrics ───────────────────────────────────────────────────────

def test_evaluation_metrics_basic():
    y_true = np.array([100.0, 102.0, 101.0, 103.0, 104.0])
    y_pred = np.array([100.5, 101.5, 101.5, 102.5, 103.5])
    m = evaluate_model(y_true, y_pred)
    assert m["mae"] == pytest.approx(0.5)
    assert m["rmse"] >= m["mae"]
    assert m["n_samples"] == 5


def test_evaluation_perfect_prediction():
    y = np.array([100.0, 101.0, 102.0, 103.0])
    m = evaluate_model(y, y)
    assert m["mae"] == pytest.approx(0) and m["r_squared"] == pytest.approx(1)


def test_evaluation_handles_nan():
    m = evaluate_model(np.array([100.0, np.nan, 102.0]), np.array([100.5, 101.0, np.nan]))
    assert m["n_samples"] == 1


def test_directional_accuracy_uses_base_price():
    base = np.array([100.0, 100.0, 100.0, 100.0])
    actual = np.array([101.0, 99.0, 102.0, 98.0])
    pred = np.array([100.5, 99.5, 99.0, 99.0])  # right, right, wrong, right
    m = evaluate_model(actual, pred, base_prices=base)
    assert m["directional_accuracy"] == pytest.approx(0.75)
    assert "skill_vs_naive" in m and "r_squared_returns" in m


def test_naive_forecast_has_zero_skill():
    base = np.array([100.0, 101.0, 102.0])
    actual = np.array([101.0, 100.0, 104.0])
    m = evaluate_model(actual, base, base_prices=base)
    assert m["skill_vs_naive"] == pytest.approx(0)


def test_select_best_model_by_rmse():
    assert select_best_model({"a": {"rmse": 2.0}, "b": {"rmse": 1.0}, "c": {"rmse": 3.0}}) == "b"


# ── Feature engineering (no look-ahead) ──────────────────────────────────────

def test_features_do_not_use_future_data():
    """Appending future rows must not change any feature already computed."""
    df = _prices(400)
    past = compute_features(df.iloc[:330])
    full = compute_features(df)
    common = past.index
    pd.testing.assert_frame_equal(past[FEATURE_COLUMNS], full.loc[common, FEATURE_COLUMNS], check_exact=False, rtol=1e-9)


def test_features_are_scale_invariant():
    df = _prices(300)
    scaled = df.copy()
    for col in ("Open", "High", "Low", "Close"):
        scaled[col] *= 10
    a, b = compute_features(df)[FEATURE_COLUMNS], compute_features(scaled)[FEATURE_COLUMNS]
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-6, atol=1e-9)


def test_target_is_forward_return():
    feats = compute_features(_prices(300))
    X, y = create_target(feats, horizon=5)
    t = X.index[10]
    expected = feats["Close"].shift(-5).loc[t] / feats["Close"].loc[t] - 1
    assert y.loc[t] == pytest.approx(expected)
    assert len(X) == len(feats) - 5


def test_purged_split_is_chronological_with_gap():
    feats = compute_features(_prices(500))
    X, y = create_target(feats, horizon=10)
    X_tr, X_va, X_te, *_ = time_series_split(X, y, gap=10)
    pos = {ts: i for i, ts in enumerate(X.index)}
    assert pos[X_va.index[0]] - pos[X_tr.index[-1]] == 11  # 10 purged rows in between
    assert pos[X_te.index[0]] - pos[X_va.index[-1]] == 11
    assert 0.65 <= len(X_tr) / len(X) <= 0.75


# ── End-to-end pipeline on simulated data ────────────────────────────────────

def test_training_pipeline_and_predictions():
    from app.ml.pipeline import TrainingPipeline, load_metadata

    meta = TrainingPipeline("KO", model_types=["linear_regression", "random_forest", "lstm"], lookback_years=4, horizons=[1, 5]).run()
    assert set(meta["horizons"]) == {"1", "5"}
    for h in meta["horizons"].values():
        assert h["best_model"] in {"linear_regression", "random_forest", "lstm"}
        for name, m in h["models"].items():
            assert "error" not in m, m
            assert m["test"]["n_samples"] > 50
            # Simulated prices are a random walk: no model should look dramatically better than naive.
            assert m["test"]["skill_vs_naive"] < 0.2
    assert load_metadata("KO")["symbol"] == "KO"


async def test_prediction_service_loads_saved_models():
    from app.services.prediction_service import PredictionService

    result = await PredictionService().get_predictions("KO")
    assert result is not None
    assert {"linear_regression", "random_forest", "lstm"} <= set(result["available_models"])
    p = result["predictions_by_model"]["random_forest"]["1d"]
    assert p["lower_bound"] < p["predicted_price"] < p["upper_bound"]
    assert len(result["forecast_path"]) == 2


async def test_training_api_job(auth_client):
    import asyncio

    r = await auth_client.post("/api/v1/predictions/train", json={"symbol": "JNJ", "model_types": ["linear_regression"]})
    assert r.status_code == 202
    for _ in range(120):
        status = (await auth_client.get("/api/v1/predictions/JNJ/status")).json()
        if status["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.5)
    assert status["status"] == "completed", status
    preds = await auth_client.get("/api/v1/predictions/JNJ")
    assert preds.status_code == 200
    ev = (await auth_client.get("/api/v1/predictions/JNJ/evaluation")).json()
    assert ev["trained"] and ev["metrics"]
    notes = (await auth_client.get("/api/v1/notifications")).json()
    assert any(n["type"] == "training_complete" for n in notes["items"])


def test_demo_history_is_deterministic_and_consistent():
    a = DemoDataProvider.history("AAPL", "1y")
    b = DemoDataProvider.history("AAPL", "1y")
    pd.testing.assert_frame_equal(a, b)
    assert a["Close"].iloc[-1] == pytest.approx(DemoDataProvider.info("AAPL")["currentPrice"])
    assert (a["High"] >= a[["Open", "Close"]].max(axis=1) - 1e-6).all()

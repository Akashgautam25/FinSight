import numpy as np
import pytest

from app.schemas.ai import OptimizationRequest
from app.services.optimization_service import OptimizationError, OptimizationService

SYMBOLS = ["AAPL", "MSFT", "JPM", "XOM", "KO"]


async def test_max_sharpe_weights_valid():
    res = await OptimizationService().optimize(OptimizationRequest(symbols=SYMBOLS), "max_sharpe")
    assert sum(res.weights.values()) == pytest.approx(1, abs=1e-3)
    assert all(0 <= w <= 1 for w in res.weights.values())


async def test_weight_bounds_respected():
    res = await OptimizationService().optimize(OptimizationRequest(symbols=SYMBOLS, max_weight=0.3), "max_sharpe")
    assert max(res.weights.values()) <= 0.3 + 1e-4


async def test_frontier_properties():
    data = await OptimizationService().compute_efficient_frontier(OptimizationRequest(symbols=SYMBOLS, investment_amount=10_000))
    ms, mv = data["max_sharpe"], data["min_volatility"]
    assert mv["volatility"] <= ms["volatility"] + 1e-6           # min-variance portfolio has the lowest risk
    assert ms["sharpe_ratio"] >= mv["sharpe_ratio"] - 1e-6       # max-Sharpe has the best Sharpe
    frontier_vols = [p["volatility"] for p in data["frontier"]]
    assert min(frontier_vols) >= mv["volatility"] - 1e-4
    # No random portfolio may beat the optimised Sharpe ratio
    assert max(p["sharpe_ratio"] for p in data["random_portfolios"]) <= ms["sharpe_ratio"] + 1e-3
    corr = np.array(data["correlation_matrix"]["matrix"])
    assert np.allclose(np.diag(corr), 1) and np.allclose(corr, corr.T)
    alloc = ms["allocation"]
    assert alloc["invested"] + alloc["leftover_cash"] == pytest.approx(10_000, abs=0.01)


async def test_infeasible_bounds_raise():
    with pytest.raises(OptimizationError):
        await OptimizationService().optimize(OptimizationRequest(symbols=["AAPL", "MSFT"], max_weight=0.3))


async def test_needs_two_valid_symbols():
    with pytest.raises(OptimizationError):
        await OptimizationService().optimize(OptimizationRequest(symbols=["AAPL", "AAPL"]))


async def test_optimizer_api_returns_400_for_bad_input(auth_client):
    r = await auth_client.post("/api/v1/optimization/max-sharpe", json={"symbols": ["AAPL", "MSFT"], "max_weight": 0.2})
    assert r.status_code == 400

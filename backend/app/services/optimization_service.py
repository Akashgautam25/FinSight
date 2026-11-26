"""
FinSight AI — Portfolio Optimization (Modern Portfolio Theory, Markowitz 1952)

Implemented directly with NumPy/SciPy:

  Inputs
    μ  expected annual returns — geometric mean (CAGR) of historical daily returns
    Σ  annual covariance — Ledoit-Wolf shrinkage estimator (more stable than the
       sample covariance when assets are few or highly correlated)

  Problems (solved with SLSQP, weights bounded by [min_weight, max_weight], Σw = 1)
    Max Sharpe       maximize (wᵀμ − r_f) / √(wᵀΣw)
    Min Volatility   minimize wᵀΣw
    Efficient return minimize wᵀΣw subject to wᵀμ = target   (traces the frontier)

  Plus a Monte Carlo cloud of random long-only portfolios for visual context.

Assumptions (shown in the UI): returns are stationary and roughly normal, past
covariance predicts future covariance, no transaction costs or taxes.
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from app.data import market_data as md
from app.schemas.ai import OptimizationRequest, OptimizationResponse

TRADING_DAYS = 252


class OptimizationError(ValueError):
    """Invalid inputs or infeasible problem (mapped to HTTP 400)."""


class _Problem:
    def __init__(self, mu: np.ndarray, cov: np.ndarray, symbols: List[str], bounds, rf: float):
        self.mu, self.cov, self.symbols, self.bounds, self.rf = mu, cov, symbols, bounds, rf
        self.n = len(symbols)
        self.sum_to_one = {"type": "eq", "fun": lambda w: np.sum(w) - 1}

    def perf(self, w: np.ndarray):
        ret = float(w @ self.mu)
        vol = float(np.sqrt(max(w @ self.cov @ w, 1e-16)))
        return ret, vol, (ret - self.rf) / vol

    def _solve(self, objective, constraints) -> np.ndarray:
        x0 = np.full(self.n, 1 / self.n)
        x0 = np.clip(x0, [b[0] for b in self.bounds], [b[1] for b in self.bounds])
        res = minimize(objective, x0, method="SLSQP", bounds=self.bounds, constraints=constraints,
                       options={"maxiter": 500, "ftol": 1e-10})
        if not res.success:
            raise OptimizationError(f"Optimizer did not converge: {res.message}")
        w = np.clip(res.x, 0, None)
        return w / w.sum()

    def max_sharpe(self) -> np.ndarray:
        def neg_sharpe(w):
            ret, vol, _ = self.perf(w)
            return -(ret - self.rf) / vol
        return self._solve(neg_sharpe, [self.sum_to_one])

    def min_volatility(self) -> np.ndarray:
        return self._solve(lambda w: w @ self.cov @ w, [self.sum_to_one])

    def efficient_return(self, target: float) -> np.ndarray:
        return self._solve(
            lambda w: w @ self.cov @ w,
            [self.sum_to_one, {"type": "eq", "fun": lambda w: w @ self.mu - target}],
        )


class OptimizationService:
    async def _problem(self, request: OptimizationRequest):
        symbols = list(dict.fromkeys(s.strip().upper() for s in request.symbols if s.strip()))
        if len(symbols) < 2:
            raise OptimizationError("Provide at least 2 distinct symbols")
        if len(symbols) > 15:
            raise OptimizationError("At most 15 symbols are supported")
        if not 0 <= request.min_weight < request.max_weight <= 1:
            raise OptimizationError("Weight bounds must satisfy 0 ≤ min_weight < max_weight ≤ 1")

        try:
            prices, demo_symbols = await md.acloses(symbols, period=request.period)
        except md.MarketDataError as exc:
            raise OptimizationError(str(exc)) from exc

        valid = [s for s in symbols if s in prices.columns]
        missing = [s for s in symbols if s not in valid]
        prices = prices[valid].dropna()
        if len(valid) < 2:
            raise OptimizationError(f"Need at least 2 symbols with price data (missing: {', '.join(missing) or 'none'})")
        if len(prices) < 60:
            raise OptimizationError("Insufficient overlapping price history (need 60+ trading days)")
        if request.max_weight * len(valid) < 1 - 1e-9:
            raise OptimizationError(f"max_weight {request.max_weight:.0%} is infeasible for {len(valid)} assets (needs ≥ {1/len(valid):.0%})")
        if request.min_weight * len(valid) > 1 + 1e-9:
            raise OptimizationError("min_weight is too large for the number of assets")

        returns = prices.pct_change().dropna()
        n_days = len(returns)
        mu = ((1 + returns).prod() ** (TRADING_DAYS / n_days) - 1).values
        cov = LedoitWolf().fit(returns.values).covariance_ * TRADING_DAYS
        bounds = [(request.min_weight, request.max_weight)] * len(valid)
        problem = _Problem(mu, cov, valid, bounds, request.risk_free_rate)
        return problem, prices, returns, missing, demo_symbols

    @staticmethod
    def _weights_dict(symbols: List[str], w: np.ndarray, threshold: float = 1e-4) -> Dict[str, float]:
        return {s: round(float(x), 4) for s, x in zip(symbols, w) if x > threshold}

    @staticmethod
    def _allocation(weights: Dict[str, float], prices: pd.DataFrame, amount: Optional[float]) -> Optional[dict]:
        """Greedy discrete allocation: whole shares as close as possible to target weights."""
        if not amount or amount <= 0:
            return None
        latest = prices.iloc[-1]
        shares, spent = {}, 0.0
        for s, w in weights.items():
            n = int((amount * w) // latest[s])
            shares[s] = n
            spent += n * float(latest[s])
        # Spend the remainder on the most under-allocated affordable asset
        while True:
            gaps = {s: amount * w - shares[s] * float(latest[s]) for s, w in weights.items()}
            affordable = [s for s in gaps if float(latest[s]) <= amount - spent]
            if not affordable:
                break
            best = max(affordable, key=lambda s: gaps[s])
            if gaps[best] <= 0:
                break
            shares[best] += 1
            spent += float(latest[best])
        return {
            "shares": {s: n for s, n in shares.items() if n > 0},
            "latest_prices": {s: round(float(latest[s]), 2) for s in weights},
            "invested": round(spent, 2),
            "leftover_cash": round(amount - spent, 2),
        }

    async def optimize(self, request: OptimizationRequest, method: str = "max_sharpe") -> OptimizationResponse:
        problem, prices, _, missing, demo_symbols = await self._problem(request)
        w = problem.max_sharpe() if method == "max_sharpe" else problem.min_volatility()
        ret, vol, sharpe = problem.perf(w)
        weights = self._weights_dict(problem.symbols, w)
        return OptimizationResponse(
            method=method,
            weights=weights,
            expected_return=round(ret, 4),
            expected_volatility=round(vol, 4),
            sharpe_ratio=round(sharpe, 4),
            efficient_frontier=None,
            allocation=self._allocation(weights, prices, request.investment_amount),
            excluded_symbols=missing,
            is_demo=bool(demo_symbols),
        )

    async def compute_efficient_frontier(self, request: OptimizationRequest) -> dict:
        problem, prices, returns, missing, demo_symbols = await self._problem(request)
        syms = problem.symbols

        w_sharpe = problem.max_sharpe()
        w_minvol = problem.min_volatility()
        special = []
        for label, w in (("Max Sharpe", w_sharpe), ("Min Volatility", w_minvol)):
            ret, vol, sharpe = problem.perf(w)
            weights = self._weights_dict(syms, w)
            special.append({
                "label": label,
                "expected_return": round(ret, 4),
                "volatility": round(vol, 4),
                "sharpe_ratio": round(sharpe, 4),
                "weights": weights,
                "allocation": self._allocation(weights, prices, request.investment_amount),
            })

        # Trace the frontier from the minimum-variance return to the max feasible return
        min_ret = problem.perf(w_minvol)[0]
        w_maxret = problem._solve(lambda w: -(w @ problem.mu), [problem.sum_to_one])
        max_ret = problem.perf(w_maxret)[0]
        frontier = []
        for target in np.linspace(min_ret, max_ret, 30):
            try:
                w = problem.efficient_return(float(target))
                ret, vol, sharpe = problem.perf(w)
                frontier.append({"expected_return": round(ret, 4), "volatility": round(vol, 4), "sharpe_ratio": round(sharpe, 4)})
            except OptimizationError:
                continue

        # Monte Carlo cloud (Dirichlet sampling = uniform over the simplex)
        rng = np.random.default_rng(42)
        cloud = []
        for w in rng.dirichlet(np.ones(len(syms)), size=1500):
            ret, vol, sharpe = problem.perf(w)
            cloud.append({"expected_return": round(ret, 4), "volatility": round(vol, 4), "sharpe_ratio": round(sharpe, 3)})

        vols = np.sqrt(np.diag(problem.cov))
        assets = [
            {"symbol": s, "expected_return": round(float(problem.mu[i]), 4), "volatility": round(float(vols[i]), 4),
             "sharpe_ratio": round(float((problem.mu[i] - problem.rf) / vols[i]), 4) if vols[i] > 0 else None}
            for i, s in enumerate(syms)
        ]
        corr = returns.corr()

        return {
            "symbols": syms,
            "excluded_symbols": missing,
            "period": request.period,
            "observations": len(returns),
            "risk_free_rate": request.risk_free_rate,
            # Kept for backward compatibility: frontier points plus the two labelled portfolios
            "efficient_frontier": frontier + special,
            "frontier": frontier,
            "max_sharpe": special[0],
            "min_volatility": special[1],
            "random_portfolios": cloud,
            "assets": assets,
            "correlation_matrix": {"symbols": list(corr.columns), "matrix": corr.round(4).values.tolist()},
            "is_demo": bool(demo_symbols),
            "demo_symbols": demo_symbols,
            "methodology": "μ: historical CAGR · Σ: Ledoit-Wolf shrinkage · solver: SLSQP (SciPy)",
            "disclaimer": (
                "Portfolio optimization is based on historical data. Past performance does not guarantee "
                "future results. This is an educational tool, not financial advice."
            ),
        }

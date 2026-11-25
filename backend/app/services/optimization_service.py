"""
FinSight AI — Portfolio Optimization Service
Implements Modern Portfolio Theory using PyPortfolioOpt.
"""

import numpy as np
import yfinance as yf

from app.schemas.ai import OptimizationRequest, OptimizationResponse


class OptimizationService:
    async def optimize(self, request: OptimizationRequest, method: str = "max_sharpe") -> OptimizationResponse:
        """
        Optimize portfolio using PyPortfolioOpt.

        method: 'max_sharpe' | 'min_volatility'

        Note: Assumes historical returns are representative of expected returns
        (sample mean). Long-only constraint applied by default.
        Optimization is based on historical covariance and expected returns —
        results are NOT guaranteed to be optimal in future markets.
        """
        from pypfopt import EfficientFrontier, risk_models, expected_returns

        # Download price data
        prices = yf.download(
            request.symbols,
            period=request.period,
            interval="1d",
            progress=False,
        )["Close"]

        if prices.empty or len(prices) < 30:
            raise ValueError("Insufficient price history for optimization")

        prices = prices.dropna(axis=1, how="all").dropna()

        # Remove any symbols with insufficient data
        valid_symbols = prices.columns.tolist()
        if len(valid_symbols) < 2:
            raise ValueError("Need at least 2 valid symbols for optimization")

        # Expected returns (mean historical return)
        mu = expected_returns.mean_historical_return(prices)

        # Covariance matrix (Ledoit-Wolf shrinkage for stability)
        S = risk_models.CovarianceShrinkage(prices).ledoit_wolf()

        # Efficient Frontier
        ef = EfficientFrontier(
            mu, S,
            weight_bounds=(request.min_weight, request.max_weight),
        )

        if method == "max_sharpe":
            ef.max_sharpe(risk_free_rate=request.risk_free_rate)
        elif method == "min_volatility":
            ef.min_volatility()

        weights = ef.clean_weights()
        expected_ret, vol, sharpe = ef.portfolio_performance(
            risk_free_rate=request.risk_free_rate, verbose=False
        )

        return OptimizationResponse(
            method=method,
            weights={k: round(v, 4) for k, v in weights.items() if v > 0.001},
            expected_return=round(float(expected_ret), 4),
            expected_volatility=round(float(vol), 4),
            sharpe_ratio=round(float(sharpe), 4),
            efficient_frontier=None,  # Populated in separate endpoint
        )

    async def compute_efficient_frontier(self, request: OptimizationRequest) -> dict:
        """Compute the full efficient frontier curve."""
        from pypfopt import EfficientFrontier, risk_models, expected_returns

        prices = yf.download(request.symbols, period=request.period, interval="1d", progress=False)["Close"]
        prices = prices.dropna(axis=1, how="all").dropna()

        mu = expected_returns.mean_historical_return(prices)
        S = risk_models.CovarianceShrinkage(prices).ledoit_wolf()

        frontier_points = []
        # Sample target returns along the frontier
        min_ret = float(mu.min())
        max_ret = float(mu.max())
        step = (max_ret - min_ret) / 20

        for target in np.arange(min_ret, max_ret, step):
            try:
                ef = EfficientFrontier(mu, S, weight_bounds=(request.min_weight, request.max_weight))
                ef.efficient_return(target_return=target)
                ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=request.risk_free_rate)
                frontier_points.append({
                    "expected_return": round(float(ret), 4),
                    "volatility": round(float(vol), 4),
                    "sharpe_ratio": round(float(sharpe), 4),
                })
            except Exception:
                continue

        # Also add max sharpe and min vol
        for method in ["max_sharpe", "min_volatility"]:
            try:
                ef = EfficientFrontier(mu, S, weight_bounds=(request.min_weight, request.max_weight))
                if method == "max_sharpe":
                    ef.max_sharpe(risk_free_rate=request.risk_free_rate)
                else:
                    ef.min_volatility()
                weights = ef.clean_weights()
                ret, vol, sharpe = ef.portfolio_performance(risk_free_rate=request.risk_free_rate)
                frontier_points.append({
                    "expected_return": round(float(ret), 4),
                    "volatility": round(float(vol), 4),
                    "sharpe_ratio": round(float(sharpe), 4),
                    "label": "Max Sharpe" if method == "max_sharpe" else "Min Volatility",
                    "weights": {k: round(v, 4) for k, v in weights.items()},
                })
            except Exception:
                pass

        # Correlation matrix
        corr_matrix = prices.pct_change().corr()
        corr_data = {
            "symbols": list(corr_matrix.columns),
            "matrix": corr_matrix.round(4).values.tolist(),
        }

        return {
            "efficient_frontier": frontier_points,
            "correlation_matrix": corr_data,
            "symbols": request.symbols,
            "period": request.period,
            "disclaimer": (
                "Portfolio optimization is based on historical data. "
                "Past performance does not guarantee future results. "
                "This is an educational tool, not financial advice."
            ),
        }

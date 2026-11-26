"""
FinSight AI — ML Model Evaluation

Metrics are computed on reconstructed *prices* (so MAE / RMSE are in currency
units and easy to interpret), plus metrics that measure real forecasting skill:

  MAE, MSE, RMSE      price error
  MAPE                mean absolute % error (rows with |actual| ≈ 0 excluded)
  R² (price)          inflated by price autocorrelation — reported for completeness
  R² (return)         the honest R²: variance of *returns* explained (≈0 is typical)
  Directional acc.    share of correct up/down calls relative to today's close
  Skill vs naive      1 − RMSE_model / RMSE_naive, where the naive (random-walk)
                      forecast is "the price stays where it is today"
"""

from typing import Dict, Optional

import numpy as np


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    if ss_tot == 0:
        return None
    return float(1 - np.sum((y_true - y_pred) ** 2) / ss_tot)


def evaluate_model(
    y_true,
    y_pred,
    split_name: str = "test",
    base_prices=None,
) -> Dict[str, Optional[float]]:
    """Compute evaluation metrics for price forecasts.

    Args:
        y_true: actual prices at the target date.
        y_pred: predicted prices at the target date.
        split_name: label stored with the metrics.
        base_prices: price on the forecast date (today's close). When given,
            directional accuracy compares each forecast with *its own* base price
            and return-space metrics are added. Without it, the previous actual
            value is used as the base (1-step-ahead convention).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    base = np.asarray(base_prices, dtype=float) if base_prices is not None else None

    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    if base is not None:
        mask &= ~np.isnan(base)
    y_true, y_pred = y_true[mask], y_pred[mask]
    base = base[mask] if base is not None else None

    empty = {"mae": None, "mse": None, "rmse": None, "mape": None, "r_squared": None,
             "directional_accuracy": None, "split": split_name, "n_samples": int(len(y_true))}
    if len(y_true) == 0:
        return empty

    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    mse = float(np.mean(err ** 2))
    rmse = float(np.sqrt(mse))
    nz = np.abs(y_true) > 1e-8
    mape = float(np.mean(np.abs(err[nz] / y_true[nz])) * 100) if nz.any() else None
    r2 = _r2(y_true, y_pred)

    result = {
        "mae": round(mae, 6),
        "mse": round(mse, 6),
        "rmse": round(rmse, 6),
        "mape": round(mape, 4) if mape is not None else None,
        "r_squared": round(r2, 6) if r2 is not None else None,
        "directional_accuracy": None,
        "split": split_name,
        "n_samples": int(len(y_true)),
    }

    if base is not None:
        actual_dir = np.sign(y_true - base)
        pred_dir = np.sign(y_pred - base)
        moved = actual_dir != 0
        result["directional_accuracy"] = round(float(np.mean(actual_dir[moved] == pred_dir[moved])), 4) if moved.any() else None
        true_ret, pred_ret = y_true / base - 1, y_pred / base - 1
        r2_ret = _r2(true_ret, pred_ret)
        result["r_squared_returns"] = round(r2_ret, 6) if r2_ret is not None else None
        naive_rmse = float(np.sqrt(np.mean((y_true - base) ** 2)))
        result["naive_rmse"] = round(naive_rmse, 6)
        result["skill_vs_naive"] = round(1 - rmse / naive_rmse, 4) if naive_rmse > 0 else None
        result["up_day_ratio"] = round(float(np.mean(actual_dir[moved] > 0)), 4) if moved.any() else None
    elif len(y_true) > 1:
        actual_dir = np.sign(np.diff(y_true))
        pred_dir = np.sign(y_pred[1:] - y_true[:-1])
        result["directional_accuracy"] = round(float(np.mean(actual_dir == pred_dir)), 4)

    return result


def select_best_model(evaluations: Dict[str, dict]) -> Optional[str]:
    """Pick the model with the lowest validation RMSE (MAE as a fallback)."""
    best_model, best_score = None, float("inf")
    for name, metrics in evaluations.items():
        score = metrics.get("rmse") if metrics.get("rmse") is not None else metrics.get("mae")
        if score is not None and score < best_score:
            best_model, best_score = name, score
    if best_model is None and evaluations:
        return next(iter(evaluations))
    return best_model

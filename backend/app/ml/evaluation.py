"""
FinSight AI — ML Model Evaluation
Computes all required metrics with mathematically correct implementations.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional


def evaluate_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    split_name: str = "test",
) -> Dict[str, Optional[float]]:
    """
    Compute MAE, MSE, RMSE, MAPE, R², and Directional Accuracy.

    MAPE is only computed when no actual value is zero (or near zero)
    to avoid division-by-zero artifacts.

    Directional Accuracy: fraction of times model correctly predicts
    up/down movement direction (lagged by 1 step).
    """
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)

    # Remove any NaN pairs
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    if len(y_true) == 0:
        return {"mae": None, "mse": None, "rmse": None, "mape": None, "r_squared": None, "directional_accuracy": None}

    mae = float(np.mean(np.abs(y_true - y_pred)))
    mse = float(np.mean((y_true - y_pred) ** 2))
    rmse = float(np.sqrt(mse))

    # MAPE — only where actual != 0
    nonzero_mask = np.abs(y_true) > 1e-8
    if nonzero_mask.sum() > 0:
        mape = float(np.mean(np.abs((y_true[nonzero_mask] - y_pred[nonzero_mask]) / y_true[nonzero_mask])) * 100)
    else:
        mape = None

    # R²
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r_squared = float(1 - ss_res / ss_tot) if ss_tot != 0 else None

    # Directional Accuracy
    if len(y_true) > 1:
        actual_direction = np.sign(np.diff(y_true))
        pred_direction = np.sign(y_pred[1:] - y_true[:-1])
        dir_acc = float(np.mean(actual_direction == pred_direction))
    else:
        dir_acc = None

    return {
        "mae": round(mae, 6),
        "mse": round(mse, 6),
        "rmse": round(rmse, 6),
        "mape": round(mape, 4) if mape is not None else None,
        "r_squared": round(r_squared, 6) if r_squared is not None else None,
        "directional_accuracy": round(dir_acc, 4) if dir_acc is not None else None,
        "split": split_name,
        "n_samples": int(len(y_true)),
    }


def select_best_model(evaluations: Dict[str, dict]) -> str:
    """
    Select best model based on RMSE on validation set.
    Falls back to MAE if RMSE is not available.
    """
    best_model = None
    best_score = float("inf")

    for model_name, eval_dict in evaluations.items():
        score = eval_dict.get("rmse") or eval_dict.get("mae")
        if score is not None and score < best_score:
            best_score = score
            best_model = model_name

    return best_model or list(evaluations.keys())[0]

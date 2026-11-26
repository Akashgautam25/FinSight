"""
FinSight AI — Forecasting Models

All models share one interface and predict the forward h-day *return*:

    fit(X_train, y_train, X_val, y_val)
    predict_full(X) -> np.ndarray   # one prediction per row of X (NaN where undefined)
    save(directory) / load(directory, symbol, horizon)

Models
  * LinearRegressionModel — ridge-regularised linear baseline
  * RandomForestModel     — bagged decision trees (non-linear, robust)
  * XGBoostModel          — gradient-boosted trees with early stopping (optional dependency)
  * LSTMModel             — 2-layer PyTorch LSTM over 20-day feature windows (optional dependency)

XGBoost and PyTorch are imported lazily: if either is missing (or XGBoost's
OpenMP runtime is not installed on macOS), that model is reported as
unavailable instead of crashing the application.
"""

from __future__ import annotations

import logging
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("finsight.ml")

# IMPORTANT (macOS): XGBoost and PyTorch ship different OpenMP runtimes. If PyTorch
# (e.g. via the FinBERT sentiment model) is loaded first, XGBoost segfaults when a
# model is loaded or used. Importing XGBoost first — here, at application start —
# avoids the conflict. app.main imports this module before anything imports torch.
try:
    import xgboost as _xgboost  # noqa: F401
except Exception:  # missing package or OpenMP runtime → XGBoost reported unavailable
    _xgboost = None

SEED = 42


def _xgboost_available() -> Optional[str]:
    try:
        import xgboost  # noqa: F401
        return None
    except Exception as exc:  # ImportError or XGBoostError (missing libomp)
        msg = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return f"XGBoost unavailable ({msg}). On macOS run: brew install libomp"


def _torch_available() -> Optional[str]:
    try:
        import torch  # noqa: F401
        return None
    except Exception as exc:
        return f"PyTorch unavailable ({exc})"


def configure_torch() -> None:
    """Run PyTorch single-threaded.

    On macOS, PyTorch and XGBoost each ship their own OpenMP runtime; once both are
    loaded in one process, multi-threaded torch kernels can deadlock. The LSTM and
    FinBERT workloads here are small, and single-threaded execution is just as fast.
    """
    import torch

    if torch.get_num_threads() != 1:
        torch.set_num_threads(1)


def model_availability() -> Dict[str, Optional[str]]:
    """Model name → None if usable, else a human-readable reason."""
    return {
        "linear_regression": None,
        "random_forest": None,
        "xgboost": _xgboost_available(),
        "lstm": _torch_available(),
    }


class BaseFinancialModel(ABC):
    model_name = "base"
    display_name = "Base"

    def __init__(self, symbol: str, horizon: int = 1):
        self.symbol = symbol
        self.horizon = horizon
        self.model = None
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.feature_columns: List[str] = []
        self.trained_at: Optional[datetime] = None
        self.hyperparameters: dict = {}

    @abstractmethod
    def fit(self, X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame, y_val: pd.Series) -> None: ...

    def _scale_fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_columns = list(X.columns)
        return (
            self.scaler_X.fit_transform(X[self.feature_columns].values),
            self.scaler_y.fit_transform(y.values.reshape(-1, 1)).ravel(),
        )

    def predict_full(self, X: pd.DataFrame) -> np.ndarray:
        X_s = self.scaler_X.transform(X[self.feature_columns].values)
        y_s = np.asarray(self.model.predict(X_s)).reshape(-1, 1)
        return self.scaler_y.inverse_transform(y_s).ravel()

    # ── persistence ─────────────────────────────────────────────────────────
    def _path(self, directory: str) -> str:
        return os.path.join(directory, f"{self.model_name}.pkl")

    def save(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = self._path(directory)
        joblib.dump({
            "model": self.model, "scaler_X": self.scaler_X, "scaler_y": self.scaler_y,
            "feature_columns": self.feature_columns, "trained_at": self.trained_at,
            "hyperparameters": self.hyperparameters,
        }, path)
        return path

    @classmethod
    def load(cls, directory: str, symbol: str, horizon: int) -> "BaseFinancialModel":
        inst = cls(symbol, horizon)
        data = joblib.load(os.path.join(directory, f"{cls.model_name}.pkl"))
        inst.model = data["model"]
        inst.scaler_X, inst.scaler_y = data["scaler_X"], data["scaler_y"]
        inst.feature_columns = data["feature_columns"]
        inst.trained_at = data.get("trained_at")
        inst.hyperparameters = data.get("hyperparameters", {})
        return inst

    def feature_importances(self) -> Dict[str, float]:
        return {}


class LinearRegressionModel(BaseFinancialModel):
    """Ridge regression baseline: interpretable, fast, resistant to collinear features."""
    model_name = "linear_regression"
    display_name = "Linear Regression"

    def fit(self, X_train, y_train, X_val, y_val):
        X_s, y_s = self._scale_fit(X_train, y_train)
        self.hyperparameters = {"alpha": 1.0}
        self.model = Ridge(alpha=1.0)
        self.model.fit(X_s, y_s)
        self.trained_at = datetime.now()

    def feature_importances(self):
        coefs = np.abs(self.model.coef_)
        return dict(zip(self.feature_columns, (coefs / coefs.sum()).tolist())) if coefs.sum() else {}


class RandomForestModel(BaseFinancialModel):
    """Random forest: captures non-linear effects, robust to outliers, gives feature importances."""
    model_name = "random_forest"
    display_name = "Random Forest"

    def fit(self, X_train, y_train, X_val, y_val):
        X_s, y_s = self._scale_fit(X_train, y_train)
        self.hyperparameters = {"n_estimators": 300, "max_depth": 6, "min_samples_leaf": 10, "max_features": 0.5}
        self.model = RandomForestRegressor(random_state=SEED, n_jobs=-1, **self.hyperparameters)
        self.model.fit(X_s, y_s)
        self.trained_at = datetime.now()

    def feature_importances(self):
        return dict(zip(self.feature_columns, self.model.feature_importances_.tolist()))


class XGBoostModel(BaseFinancialModel):
    """Gradient-boosted trees with early stopping on the validation set."""
    model_name = "xgboost"
    display_name = "XGBoost"

    def fit(self, X_train, y_train, X_val, y_val):
        from xgboost import XGBRegressor

        X_s, y_s = self._scale_fit(X_train, y_train)
        X_v = self.scaler_X.transform(X_val[self.feature_columns].values)
        y_v = self.scaler_y.transform(y_val.values.reshape(-1, 1)).ravel()
        self.hyperparameters = {
            "n_estimators": 600, "learning_rate": 0.03, "max_depth": 3, "subsample": 0.8,
            "colsample_bytree": 0.8, "min_child_weight": 5, "reg_lambda": 1.0,
        }
        self.model = XGBRegressor(early_stopping_rounds=50, random_state=SEED, n_jobs=-1, verbosity=0, **self.hyperparameters)
        self.model.fit(X_s, y_s, eval_set=[(X_v, y_v)], verbose=False)
        self.hyperparameters["best_iteration"] = int(getattr(self.model, "best_iteration", 0) or 0)
        self.trained_at = datetime.now()

    def feature_importances(self):
        return dict(zip(self.feature_columns, self.model.feature_importances_.astype(float).tolist()))


class LSTMModel(BaseFinancialModel):
    """Two-layer LSTM over sliding windows of the last `sequence_length` days of features.

    A window ending on day t (rows t-L+1 … t) predicts the target of day t, so
    training and inference use exactly the same alignment.
    """
    model_name = "lstm"
    display_name = "LSTM (PyTorch)"

    def __init__(self, symbol: str, horizon: int = 1, sequence_length: int = 20,
                 hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super().__init__(symbol, horizon)
        self.sequence_length = sequence_length
        self.hidden_size, self.num_layers, self.dropout = hidden_size, num_layers, dropout
        self.net = None

    def _build(self, input_size: int):
        import torch.nn as nn

        class LSTMNet(nn.Module):
            def __init__(self, n_in, hidden, layers, drop):
                super().__init__()
                self.lstm = nn.LSTM(n_in, hidden, num_layers=layers, batch_first=True, dropout=drop if layers > 1 else 0)
                self.head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Dropout(drop), nn.Linear(32, 1))

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :])

        return LSTMNet(input_size, self.hidden_size, self.num_layers, self.dropout)

    def _windows(self, X_s: np.ndarray, end_indices: np.ndarray) -> np.ndarray:
        L = self.sequence_length
        return np.stack([X_s[i - L + 1:i + 1] for i in end_indices]).astype(np.float32)

    def fit(self, X_train, y_train, X_val, y_val):
        import torch

        torch.manual_seed(SEED)
        np.random.seed(SEED)
        random.seed(SEED)
        configure_torch()

        X_tr_s, y_tr_s = self._scale_fit(X_train, y_train)
        X_val_s = self.scaler_X.transform(X_val[self.feature_columns].values)
        y_val_s = self.scaler_y.transform(y_val.values.reshape(-1, 1)).ravel()
        L = self.sequence_length
        if len(X_tr_s) <= L + 10:
            raise ValueError("Insufficient data for LSTM sequences")

        # Validation windows may reach back into the end of the training block (features only).
        combined = np.vstack([X_tr_s, X_val_s])
        tr_idx = np.arange(L - 1, len(X_tr_s))
        val_idx = np.arange(len(X_tr_s), len(combined))
        Xtr = torch.from_numpy(self._windows(combined, tr_idx))
        ytr = torch.from_numpy(y_tr_s[tr_idx].astype(np.float32)).unsqueeze(1)
        Xv = torch.from_numpy(self._windows(combined, val_idx))
        yv = torch.from_numpy(y_val_s.astype(np.float32)).unsqueeze(1)

        self.net = self._build(len(self.feature_columns))
        opt = torch.optim.Adam(self.net.parameters(), lr=1e-3, weight_decay=1e-5)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=5, factor=0.5)
        loss_fn = torch.nn.MSELoss()
        best, best_state, patience, bad = float("inf"), None, 12, 0
        gen = torch.Generator().manual_seed(SEED)
        epochs_run = 0

        for epoch in range(80):
            self.net.train()
            for batch in torch.randperm(len(Xtr), generator=gen).split(64):
                opt.zero_grad()
                loss = loss_fn(self.net(Xtr[batch]), ytr[batch])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                opt.step()
            self.net.eval()
            with torch.no_grad():
                val_loss = loss_fn(self.net(Xv), yv).item()
            sched.step(val_loss)
            epochs_run = epoch + 1
            if val_loss < best - 1e-6:
                best, bad = val_loss, 0
                best_state = {k: v.detach().clone() for k, v in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break

        if best_state:
            self.net.load_state_dict(best_state)
        self.net.eval()
        self.model = self.net
        self.hyperparameters = {
            "sequence_length": L, "hidden_size": self.hidden_size, "num_layers": self.num_layers,
            "dropout": self.dropout, "optimizer": "Adam(lr=1e-3)", "batch_size": 64,
            "epochs_run": epochs_run, "best_val_mse_scaled": round(best, 6),
        }
        self.trained_at = datetime.now()

    def predict_full(self, X: pd.DataFrame) -> np.ndarray:
        import torch

        X_s = self.scaler_X.transform(X[self.feature_columns].values)
        L = self.sequence_length
        out = np.full(len(X_s), np.nan)
        if len(X_s) < L:
            return out
        idx = np.arange(L - 1, len(X_s))
        with torch.no_grad():
            preds = self.net(torch.from_numpy(self._windows(X_s, idx))).numpy()
        out[idx] = self.scaler_y.inverse_transform(preds).ravel()
        return out

    def save(self, directory: str) -> str:
        import torch

        os.makedirs(directory, exist_ok=True)
        weights_path = os.path.join(directory, "lstm.pt")
        torch.save(self.net.state_dict(), weights_path)  # tensors only → safe weights_only loading
        joblib.dump({
            "scaler_X": self.scaler_X, "scaler_y": self.scaler_y, "feature_columns": self.feature_columns,
            "trained_at": self.trained_at, "hyperparameters": self.hyperparameters,
            "config": {"sequence_length": self.sequence_length, "hidden_size": self.hidden_size,
                       "num_layers": self.num_layers, "dropout": self.dropout},
        }, os.path.join(directory, "lstm.meta.pkl"))
        return weights_path

    @classmethod
    def load(cls, directory: str, symbol: str, horizon: int) -> "LSTMModel":
        import torch

        configure_torch()
        meta = joblib.load(os.path.join(directory, "lstm.meta.pkl"))
        inst = cls(symbol, horizon, **meta["config"])
        inst.scaler_X, inst.scaler_y = meta["scaler_X"], meta["scaler_y"]
        inst.feature_columns = meta["feature_columns"]
        inst.trained_at = meta.get("trained_at")
        inst.hyperparameters = meta.get("hyperparameters", {})
        inst.net = inst._build(len(inst.feature_columns))
        inst.net.load_state_dict(torch.load(os.path.join(directory, "lstm.pt"), weights_only=True))
        inst.net.eval()
        inst.model = inst.net
        return inst


MODEL_REGISTRY = {
    "linear_regression": LinearRegressionModel,
    "random_forest": RandomForestModel,
    "xgboost": XGBoostModel,
    "lstm": LSTMModel,
}

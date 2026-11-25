"""
FinSight AI — ML Models Implementation
Linear Regression, Random Forest, XGBoost, LSTM
"""

import os
import joblib
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict
from datetime import datetime

import torch
import torch.nn as nn
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBRegressor

from app.config import settings


class BaseFinancialModel(ABC):
    """Abstract base for all FinSight prediction models."""

    def __init__(self, symbol: str, horizon: int = 1):
        self.symbol = symbol
        self.horizon = horizon
        self.model = None
        self.scaler_X = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        self.feature_columns: list = []
        self.trained_at: Optional[datetime] = None
        self.model_version: str = datetime.now().strftime("%Y%m%d_%H%M%S")

    @abstractmethod
    def fit(self, X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame, y_val: pd.Series):
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        pass

    def save(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{self.model_name}_{self.symbol}_h{self.horizon}_{self.model_version}.pkl")
        joblib.dump({
            "model": self.model,
            "scaler_X": self.scaler_X,
            "scaler_y": self.scaler_y,
            "feature_columns": self.feature_columns,
            "trained_at": self.trained_at,
            "model_version": self.model_version,
        }, path)
        return path

    @classmethod
    def load(cls, path: str, symbol: str, horizon: int):
        data = joblib.load(path)
        instance = cls.__new__(cls)
        instance.symbol = symbol
        instance.horizon = horizon
        instance.model = data["model"]
        instance.scaler_X = data["scaler_X"]
        instance.scaler_y = data["scaler_y"]
        instance.feature_columns = data["feature_columns"]
        instance.trained_at = data.get("trained_at")
        instance.model_version = data.get("model_version", "unknown")
        return instance


class LinearRegressionModel(BaseFinancialModel):
    """
    Baseline linear regression model.
    Selected as baseline to benchmark more complex models against.
    Simple, interpretable, low computational cost.
    """
    model_name = "linear_regression"

    def fit(self, X_train, y_train, X_val, y_val):
        self.feature_columns = list(X_train.columns)
        X_scaled = self.scaler_X.fit_transform(X_train[self.feature_columns])
        y_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1)).ravel()
        self.model = LinearRegression()
        self.model.fit(X_scaled, y_scaled)
        self.trained_at = datetime.now()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler_X.transform(X[self.feature_columns])
        y_scaled = self.model.predict(X_scaled).reshape(-1, 1)
        return self.scaler_y.inverse_transform(y_scaled).ravel()


class RandomForestModel(BaseFinancialModel):
    """
    Random Forest Regressor.
    Selected for: handles non-linear relationships, robust to outliers,
    built-in feature importance, low overfitting risk via ensemble.
    """
    model_name = "random_forest"

    def fit(self, X_train, y_train, X_val, y_val):
        self.feature_columns = list(X_train.columns)
        X_scaled = self.scaler_X.fit_transform(X_train[self.feature_columns])
        y_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1)).ravel()
        self.model = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_scaled, y_scaled)
        self.trained_at = datetime.now()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler_X.transform(X[self.feature_columns])
        y_scaled = self.model.predict(X_scaled).reshape(-1, 1)
        return self.scaler_y.inverse_transform(y_scaled).ravel()

    def feature_importances(self) -> Dict[str, float]:
        if self.model and hasattr(self.model, "feature_importances_"):
            return dict(zip(self.feature_columns, self.model.feature_importances_))
        return {}


class XGBoostModel(BaseFinancialModel):
    """
    XGBoost Regressor.
    Selected for: gradient boosting captures complex patterns,
    handles mixed features efficiently, early stopping on validation.
    """
    model_name = "xgboost"

    def fit(self, X_train, y_train, X_val, y_val):
        self.feature_columns = list(X_train.columns)
        X_tr_scaled = self.scaler_X.fit_transform(X_train[self.feature_columns])
        y_tr_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1)).ravel()
        X_val_scaled = self.scaler_X.transform(X_val[self.feature_columns])
        y_val_scaled = self.scaler_y.transform(y_val.values.reshape(-1, 1)).ravel()

        self.model = XGBRegressor(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            early_stopping_rounds=50,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )
        self.model.fit(
            X_tr_scaled, y_tr_scaled,
            eval_set=[(X_val_scaled, y_val_scaled)],
            verbose=False,
        )
        self.trained_at = datetime.now()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler_X.transform(X[self.feature_columns])
        y_scaled = self.model.predict(X_scaled).reshape(-1, 1)
        return self.scaler_y.inverse_transform(y_scaled).ravel()


# ── LSTM ──────────────────────────────────────────────────────────────────────

class LSTMNet(nn.Module):
    """
    LSTM architecture for time-series prediction.
    2-layer LSTM with dropout regularization.
    """

    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class LSTMModel(BaseFinancialModel):
    """
    LSTM Neural Network for sequential pattern learning.
    Selected for: captures temporal dependencies, handles non-linear
    time-series patterns, state-of-the-art for financial forecasting.
    Uses PyTorch with CPU/GPU support.
    """
    model_name = "lstm"

    def __init__(self, symbol: str, horizon: int = 1, sequence_length: int = 20):
        super().__init__(symbol, horizon)
        self.sequence_length = sequence_length
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net: Optional[LSTMNet] = None

    def _create_sequences(self, X_scaled: np.ndarray, y_scaled: np.ndarray) -> Tuple:
        Xs, ys = [], []
        for i in range(self.sequence_length, len(X_scaled)):
            Xs.append(X_scaled[i - self.sequence_length:i])
            ys.append(y_scaled[i])
        return np.array(Xs), np.array(ys)

    def fit(self, X_train, y_train, X_val, y_val):
        self.feature_columns = list(X_train.columns)

        X_tr_scaled = self.scaler_X.fit_transform(X_train[self.feature_columns])
        y_tr_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1))
        X_val_scaled = self.scaler_X.transform(X_val[self.feature_columns])
        y_val_scaled = self.scaler_y.transform(y_val.values.reshape(-1, 1))

        X_tr_seq, y_tr_seq = self._create_sequences(X_tr_scaled, y_tr_scaled)
        X_val_seq, y_val_seq = self._create_sequences(X_val_scaled, y_val_scaled)

        if len(X_tr_seq) == 0:
            raise ValueError("Insufficient data for LSTM sequence creation")

        X_tr_t = torch.FloatTensor(X_tr_seq).to(self.device)
        y_tr_t = torch.FloatTensor(y_tr_seq).to(self.device)
        X_val_t = torch.FloatTensor(X_val_seq).to(self.device)
        y_val_t = torch.FloatTensor(y_val_seq).to(self.device)

        self.net = LSTMNet(
            input_size=len(self.feature_columns),
            hidden_size=128,
            num_layers=2,
            dropout=0.2,
        ).to(self.device)

        optimizer = torch.optim.Adam(self.net.parameters(), lr=1e-3, weight_decay=1e-5)
        criterion = nn.MSELoss()
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

        best_val_loss = float("inf")
        patience_counter = 0
        patience = 20

        for epoch in range(100):
            self.net.train()
            optimizer.zero_grad()
            pred = self.net(X_tr_t)
            loss = criterion(pred, y_tr_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
            optimizer.step()

            self.net.eval()
            with torch.no_grad():
                val_pred = self.net(X_val_t)
                val_loss = criterion(val_pred, y_val_t).item()

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break

        self.net.load_state_dict(best_state)
        self.model = self.net
        self.trained_at = datetime.now()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler_X.transform(X[self.feature_columns])
        # For prediction: use last sequence_length rows
        if len(X_scaled) < self.sequence_length:
            raise ValueError("Not enough data for LSTM prediction sequence")

        sequences = []
        for i in range(self.sequence_length, len(X_scaled) + 1):
            seq = X_scaled[i - self.sequence_length:i]
            sequences.append(seq)

        X_t = torch.FloatTensor(np.array(sequences)).to(self.device)
        self.net.eval()
        with torch.no_grad():
            y_scaled = self.net(X_t).cpu().numpy()

        return self.scaler_y.inverse_transform(y_scaled).ravel()

    def save(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"lstm_{self.symbol}_h{self.horizon}_{self.model_version}.pt")
        torch.save({
            "net_state": self.net.state_dict(),
            "net_config": {
                "input_size": len(self.feature_columns),
                "hidden_size": 128,
                "num_layers": 2,
                "dropout": 0.2,
            },
            "scaler_X": self.scaler_X,
            "scaler_y": self.scaler_y,
            "feature_columns": self.feature_columns,
            "sequence_length": self.sequence_length,
            "trained_at": self.trained_at,
            "model_version": self.model_version,
        }, path)
        return path

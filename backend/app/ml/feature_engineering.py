"""
FinSight AI — ML Feature Engineering
Implements time-aware feature computation without look-ahead bias.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical and statistical features for ML models.
    All features use only past data (no look-ahead).

    Args:
        df: DataFrame with columns [Open, High, Low, Close, Volume]
            indexed by date, sorted ascending.

    Returns:
        DataFrame with original OHLCV columns + engineered features.
        Rows with NaN in any feature column are dropped.
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index(ascending=True)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # ── Returns ──────────────────────────────────────────────────────────────
    df["daily_return"] = close.pct_change()
    df["log_return"] = np.log(close / close.shift(1))

    # ── Moving Averages ──────────────────────────────────────────────────────
    for window in [5, 10, 20, 50, 200]:
        df[f"sma_{window}"] = close.rolling(window).mean()

    df["ema_12"] = close.ewm(span=12, adjust=False).mean()
    df["ema_26"] = close.ewm(span=26, adjust=False).mean()

    # MA ratios (normalized)
    df["close_to_sma20"] = close / df["sma_20"]
    df["close_to_sma50"] = close / df["sma_50"]
    df["sma20_to_sma50"] = df["sma_20"] / df["sma_50"]

    # ── RSI ──────────────────────────────────────────────────────────────────
    df["rsi_14"] = _compute_rsi(close, 14)

    # ── MACD ─────────────────────────────────────────────────────────────────
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / bb_mid
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # ── Volatility ────────────────────────────────────────────────────────────
    df["volatility_10"] = df["daily_return"].rolling(10).std()
    df["volatility_20"] = df["daily_return"].rolling(20).std()

    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr_14"] / close

    # ── Momentum ─────────────────────────────────────────────────────────────
    for period in [5, 10, 20]:
        df[f"momentum_{period}"] = close / close.shift(period) - 1

    # Rate of change
    df["roc_5"] = close.pct_change(5)
    df["roc_10"] = close.pct_change(10)

    # ── Volume Features ───────────────────────────────────────────────────────
    df["volume_sma_20"] = volume.rolling(20).mean()
    df["volume_ratio"] = volume / df["volume_sma_20"]
    df["obv"] = (np.sign(df["daily_return"]) * volume).cumsum()

    # ── Lagged Returns ────────────────────────────────────────────────────────
    for lag in [1, 2, 3, 5, 10]:
        df[f"lag_return_{lag}"] = df["daily_return"].shift(lag)
        df[f"lag_close_{lag}"] = close.shift(lag)

    # ── Lagged Close (normalized) ─────────────────────────────────────────────
    for lag in [1, 2, 3]:
        df[f"lag_close_norm_{lag}"] = close.shift(lag) / close.shift(lag + 1)

    # Drop NaN rows (from rolling/lagged features)
    df = df.dropna()

    return df


def _compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window, min_periods=window).mean()
    avg_loss = loss.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def create_target(df: pd.DataFrame, horizon: int = 1) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Create target variable: future close price N days ahead.
    Uses shift(-horizon) which must only be applied AFTER the train/test split
    boundary is enforced — target is never computed on the test set using
    future data from beyond the split.

    Returns X (features) and y (target) aligned by index.
    """
    target = df["Close"].shift(-horizon)
    X = df.iloc[:-horizon]
    y = target.iloc[:-horizon]
    return X, y


FEATURE_COLUMNS = [
    "daily_return", "log_return",
    "sma_5", "sma_10", "sma_20", "sma_50",
    "ema_12", "ema_26",
    "close_to_sma20", "close_to_sma50", "sma20_to_sma50",
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    "bb_width", "bb_pct",
    "volatility_10", "volatility_20",
    "atr_pct",
    "momentum_5", "momentum_10", "momentum_20",
    "roc_5", "roc_10",
    "volume_ratio",
    "lag_return_1", "lag_return_2", "lag_return_3", "lag_return_5", "lag_return_10",
    "lag_close_norm_1", "lag_close_norm_2", "lag_close_norm_3",
]


def time_series_split(
    X: pd.DataFrame,
    y: pd.Series,
    train_pct: float = 0.70,
    val_pct: float = 0.15,
) -> Tuple:
    """
    Strictly chronological train/validation/test split.
    No shuffling. No random state. Time order is always preserved.
    """
    n = len(X)
    train_end = int(n * train_pct)
    val_end = int(n * (train_pct + val_pct))

    X_train = X.iloc[:train_end]
    y_train = y.iloc[:train_end]
    X_val = X.iloc[train_end:val_end]
    y_val = y.iloc[train_end:val_end]
    X_test = X.iloc[val_end:]
    y_test = y.iloc[val_end:]

    return X_train, X_val, X_test, y_train, y_val, y_test

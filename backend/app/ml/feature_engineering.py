"""
FinSight AI — ML Feature Engineering

Design decisions (documented in docs/ml_documentation.md):

* **No look-ahead.** Every feature at day t uses data up to and including day t.
* **Scale-invariant features.** Raw price levels (e.g. SMA-50 = 412.3) are
  non-stationary and break when a stock trades outside its training range.
  All features are ratios, returns or bounded oscillators instead.
* **Return target.** Models predict the forward h-day return
  r = Close[t+h] / Close[t] − 1, which is converted back to a price with
  Close[t] · (1 + r). Tree models cannot extrapolate price levels, but they can
  predict returns at any price level.
* **Purged chronological split.** Train / validation / test are contiguous
  blocks in time, and `horizon` rows are dropped at each boundary so no
  training label overlaps the validation or test period.
"""

from typing import Tuple

import numpy as np
import pandas as pd

from app.ml import indicators as ind

FEATURE_COLUMNS = [
    # returns
    "daily_return", "log_return", "high_low_range",
    # trend (price relative to moving averages)
    "close_to_sma5", "close_to_sma10", "close_to_sma20", "close_to_sma50", "close_to_sma200",
    "sma20_to_sma50", "sma50_to_sma200", "ema12_to_ema26",
    # oscillators
    "rsi_14", "macd_norm", "macd_signal_norm", "macd_hist_norm", "bb_width", "bb_pct",
    # volatility
    "volatility_10", "volatility_20", "atr_pct",
    # momentum
    "momentum_5", "momentum_10", "momentum_20", "roc_5", "roc_10",
    # volume
    "volume_ratio", "obv_slope",
    # autoregressive lags
    "lag_return_1", "lag_return_2", "lag_return_3", "lag_return_5", "lag_return_10",
]

MIN_ROWS = 260  # SMA-200 warm-up + enough samples to train on


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features to an OHLCV frame (sorted ascending, indexed by date).

    Rows where any feature is undefined (indicator warm-up) are dropped.
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"].astype(float)

    df["daily_return"] = close.pct_change()
    df["log_return"] = np.log(close / close.shift(1))
    df["high_low_range"] = (high - low) / close

    sma = {w: ind.sma(close, w) for w in (5, 10, 20, 50, 200)}
    for w, s in sma.items():
        df[f"close_to_sma{w}"] = close / s - 1
    df["sma20_to_sma50"] = sma[20] / sma[50] - 1
    df["sma50_to_sma200"] = sma[50] / sma[200] - 1
    ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    df["ema12_to_ema26"] = ema12 / ema26 - 1

    df["rsi_14"] = ind.rsi(close) / 100.0
    macd_line, macd_sig, macd_hist = ind.macd(close)
    df["macd_norm"] = macd_line / close
    df["macd_signal_norm"] = macd_sig / close
    df["macd_hist_norm"] = macd_hist / close
    bb_up, bb_mid, bb_low = ind.bollinger(close)
    df["bb_width"] = (bb_up - bb_low) / bb_mid
    df["bb_pct"] = (close - bb_low) / (bb_up - bb_low).replace(0, np.nan)

    df["volatility_10"] = df["daily_return"].rolling(10).std()
    df["volatility_20"] = df["daily_return"].rolling(20).std()
    df["atr_pct"] = ind.atr(high, low, close) / close

    for p in (5, 10, 20):
        df[f"momentum_{p}"] = close / close.shift(p) - 1
    df["roc_5"] = df["daily_return"].rolling(5).sum()
    df["roc_10"] = df["daily_return"].rolling(10).sum()

    vol_sma20 = volume.rolling(20).mean()
    df["volume_ratio"] = volume / vol_sma20.replace(0, np.nan)
    obv = (np.sign(df["daily_return"]).fillna(0) * volume).cumsum()
    df["obv_slope"] = obv.diff(10) / (vol_sma20.replace(0, np.nan) * 10)

    for lag in (1, 2, 3, 5, 10):
        df[f"lag_return_{lag}"] = df["daily_return"].shift(lag)

    df = df.replace([np.inf, -np.inf], np.nan)
    return df.dropna(subset=FEATURE_COLUMNS)


def create_target(df: pd.DataFrame, horizon: int = 1) -> Tuple[pd.DataFrame, pd.Series]:
    """Forward h-day return target. The last `horizon` rows (no future yet) are removed.

    Returns (X_frame, y_return) aligned on the same index. X_frame still contains
    the Close column, which the pipeline uses to convert returns back to prices.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    future_return = df["Close"].shift(-horizon) / df["Close"] - 1
    X = df.iloc[:-horizon]
    y = future_return.iloc[:-horizon]
    return X, y


def time_series_split(
    X: pd.DataFrame,
    y: pd.Series,
    train_pct: float = 0.70,
    val_pct: float = 0.15,
    gap: int = 0,
) -> Tuple:
    """Strictly chronological train/validation/test split (no shuffling).

    `gap` rows are purged after the train block and after the validation block
    so that labels spanning `gap` days cannot leak across the boundaries.
    """
    n = len(X)
    train_end = int(n * train_pct)
    val_start = train_end + gap
    val_end = int(n * (train_pct + val_pct))
    test_start = val_end + gap
    if val_start >= val_end or test_start >= n:
        raise ValueError("Not enough rows for a purged train/validation/test split")

    return (
        X.iloc[:train_end], X.iloc[val_start:val_end], X.iloc[test_start:],
        y.iloc[:train_end], y.iloc[val_start:val_end], y.iloc[test_start:],
    )

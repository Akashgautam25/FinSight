"""
FinSight AI — Technical Indicators (pure pandas implementations)

Shared by the stock-analysis API and the ML feature pipeline. Every indicator
at time t uses only data up to and including t (no look-ahead).
"""

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing (the industry-standard definition)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    # No losses in the window → RSI is 100 by definition
    return out.where(avg_loss != 0, 100.0).where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram)."""
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0):
    """Returns (upper, middle, lower). Uses population std (ddof=0) as in Bollinger's definition."""
    mid = close.rolling(window, min_periods=window).mean()
    std = close.rolling(window, min_periods=window).std(ddof=0)
    return mid + num_std * std, mid, mid - num_std * std


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range with Wilder's smoothing."""
    return true_range(high, low, close).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def add_chart_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Overlay columns used by the interactive price chart."""
    out = df.copy()
    close = out["Close"]
    out["sma_20"] = sma(close, 20)
    out["sma_50"] = sma(close, 50)
    out["sma_200"] = sma(close, 200)
    out["bb_upper"], _, out["bb_lower"] = bollinger(close)
    out["rsi_14"] = rsi(close)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(close)
    return out

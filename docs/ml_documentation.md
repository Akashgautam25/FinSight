# FinSight AI — Machine Learning & Quantitative Modeling Documentation

## 1. Problem Formulation
Stock price prediction is formulated as a supervised regression task over sequential historical market observations. Given an asset's historical feature matrix $X_{1:t} \in \mathbb{R}^{t \times d}$, predict the future price at horizon $h$:
$$\hat{y}_{t+h} = f_\theta(X_{1:t})$$
where $h \in \{1, 5, 10, 30\}$ trading days.

---

## 2. Feature Engineering Pipeline
The feature extraction pipeline computes 35+ quantitative indicators:
- **Returns**: Daily percentage returns, logarithmic returns.
- **Trend**: SMA (5, 10, 20, 50, 200), EMA (12, 26), moving average ratios ($Close/SMA_{20}$, $SMA_{20}/SMA_{50}$).
- **Momentum**: RSI (14 days), MACD line, signal line, MACD histogram, Rate of Change (ROC-5, ROC-10).
- **Volatility**: Bollinger Bands (upper, lower, bandwidth, %B), 10-day & 20-day rolling return standard deviation, Average True Range (ATR-14).
- **Volume**: 20-day volume moving average, volume ratio ($Vol / SMA_{20}(Vol)$), On-Balance Volume (OBV).
- **Autoregressive Lags**: Lagged returns at $t-1, t-2, t-3, t-5, t-10$.

---

## 3. Data Leakage Prevention Protocol
1. **Strict Chronological Splitting**:
   - Train: First 70% of chronological observations.
   - Validation: Subsequent 15% of observations.
   - Test: Final 15% out-of-sample observations.
   - **No random shuffling or k-fold cross-validation** is permitted on time series.
2. **Scaler Isolation**:
   - `MinMaxScaler` is fit **exclusively** on the training partition ($X_{train}, y_{train}$) and used to transform validation and test sets.
3. **Feature Windowing**:
   - Target shifting (`shift(-h)`) is executed strictly before normalization.

---

## 4. Evaluated Architectures
1. **Baseline Linear Regression**: Ordinary Least Squares baseline benchmark.
2. **Random Forest Regressor**: 200 estimators, maximum tree depth of 10, minimum leaf samples of 5.
3. **XGBoost Regressor**: Gradient boosted decision trees optimizing mean squared error with learning rate $\eta = 0.05$, early stopping rounds of 50 on validation loss, and feature subsampling ($colsample = 0.8$).
4. **PyTorch LSTM**: 2 stacked LSTM recurrent layers with 128 hidden dimensions, dropout probability $p = 0.2$, sequence length of 20 days, and Adam optimizer with `ReduceLROnPlateau` scheduler.

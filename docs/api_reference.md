# FinSight AI — REST API Reference Guide

Interactive OpenAPI / Swagger documentation is accessible at `/docs` when the backend is active.

### Base URL: `/api/v1`

---

### Authentication (`/auth`)
- `POST /auth/register`: Register user account and receive initial JWT access and refresh token pair.
- `POST /auth/login`: Authenticate email and password.
- `POST /auth/refresh`: Exchange valid refresh token for a refreshed access token.
- `GET /auth/me`: Retrieve current authenticated user profile.
- `PATCH /auth/me`: Update profile details, base currency, and time zone.

---

### Stocks & Market Intelligence (`/stocks`)
- `GET /stocks/search?q={query}`: Search equity universe by company name or ticker symbol.
- `GET /stocks/market/overview`: Returns major index performance (S&P 500, NASDAQ, Dow, NIFTY 50).
- `GET /stocks/{symbol}`: Comprehensive overview, quotes, and fundamentals.
- `GET /stocks/{symbol}/history?period={1y}&interval={1d}`: OHLCV time-series series.
- `GET /stocks/{symbol}/technical`: SMA, EMA, RSI(14), MACD, Bollinger Bands, and ATR.
- `GET /stocks/compare?symbols=AAPL,MSFT,NVDA`: Comparative multi-stock benchmarking.

---

### Machine Learning Predictions (`/predictions`)
- `POST /predictions/train`: Asynchronously queue model training (LR, RF, XGBoost, LSTM) for a given symbol.
- `GET /predictions/{symbol}`: Multi-horizon forecasts (1, 5, 10, 30 days) comparing all trained models.
- `GET /predictions/{symbol}/evaluation`: Evaluation metrics (MAE, RMSE, MAPE, R², Directional Accuracy).

---

### News & Sentiment (`/news`)
- `GET /news`: General financial news with FinBERT sentiment classification.
- `GET /news/{symbol}`: Company-specific news articles and scores.
- `GET /news/{symbol}/sentiment`: Aggregated institutional sentiment distribution (positive/negative/neutral %).

---

### Portfolio Management (`/portfolios`)
- `GET /portfolios`: List user portfolios.
- `POST /portfolios`: Create a portfolio.
- `GET /portfolios/{id}/analytics`: Compute total invested capital, current value, P&L, Sharpe ratio, volatility, and max drawdown.
- `POST /portfolios/{id}/transactions`: Record BUY or SELL execution.

---

### Portfolio Optimization (`/optimization`)
- `POST /optimization/efficient-frontier`: Compute Markowitz Efficient Frontier curve and asset correlation matrix.
- `POST /optimization/max-sharpe`: Calculate optimal weights maximizing Sharpe Ratio.
- `POST /optimization/min-volatility`: Calculate weights minimizing portfolio variance.

---

### AI Financial Assistant (`/ai`)
- `POST /ai/chat`: Send financial research query to LangGraph agent with tool calling and source citations.
- `POST /ai/generate-report`: Synthesize institutional research dossier and compile PDF.

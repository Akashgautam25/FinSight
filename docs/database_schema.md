# FinSight AI — Database Schema Specification

The schema runs on **SQLite** (default, zero-config) or **PostgreSQL 16** (Docker/production). Primary keys are UUID strings; semi-structured fields use JSON (mapped to JSONB on PostgreSQL). Tables are created automatically at startup. All user-owned rows cascade-delete with their owner.

## Tables Summary

1. **`users`**: User account credentials, email, verification status, and role.
2. **`user_profiles`**: User biographical info, avatar, base currency, and notification preferences.
3. **`user_preferences`**: UI theme (dark/light), default market universe, and dashboard widget layouts.
4. **`portfolios`**: User investment portfolios with base reporting currency and metadata.
5. **`portfolio_holdings`**: Normalized aggregate asset positions per portfolio (symbol, quantity, avg purchase price).
6. **`portfolio_transactions`**: Ledger of individual BUY and SELL execution orders with timestamp, price, and fees.
7. **`watchlists`**: User-defined stock watchlists.
8. **`watchlist_stocks`**: Many-to-many junction tracking stocks in watchlists with custom sorting orders.
9. **`stocks`**: Master directory of tracked equity securities (ticker, exchange, sector, industry, country).
10. **`stock_prices`**: Historical OHLCV end-of-day price observations indexed by `(symbol, price_date)`.
11. **`financial_metrics`**: Fundamental valuation and performance ratios (P/E, EPS, Beta, ROE, ROA, Debt-to-Equity, FCF).
12. **`stock_news`**: Aggregated market news headlines and summaries with cryptographic MD5 deduplication hash.
13. **`sentiment_analysis`**: FinBERT classification scores (positive, negative, neutral, compound) per news article.
14. **`ml_models`**: Catalog of trained model artifacts, hyperparameters, feature schema, and version identifiers.
15. **`model_evaluations`**: Quantitative test performance records (MAE, RMSE, MAPE, R², Directional Accuracy).
16. **`model_predictions`**: Forecasted price targets per horizon (1, 5, 10, 30 days) with confidence intervals.
17. **`research_reports`**: Programmatically compiled equity research documents with JSON payload and PDF export paths.
18. **`chat_sessions`**: Conversational threads initiated with the AI Research Assistant.
19. **`chat_messages`**: Chat history records storing prompt, response, sources, and verified tool executions.
20. **`price_alerts`**: User-defined threshold notifications (price above, price below, daily % change).
21. **`notifications`**: In-app alert queue for triggered price conditions and completed background model training.

## Usage status

| Table(s) | Used by |
|---|---|
| users, user_profiles, user_preferences | Auth, profile & settings |
| portfolios, portfolio_holdings, portfolio_transactions | Portfolio manager (holdings rebuilt from the transaction ledger) |
| watchlists, watchlist_stocks | Watchlists |
| stocks | Security master — cached company profiles (name, sector, currency), refreshed monthly |
| ml_models, model_evaluations | One row per trained model/horizon and its validation/test metrics |
| research_reports | Generated reports (JSON payload + PDF path) |
| chat_sessions, chat_messages | Assistant history with sources and tool calls |
| price_alerts, notifications | Alerts and in-app notifications |
| stock_prices, financial_metrics, stock_news, sentiment_analysis, model_predictions | Reserved for historical persistence (current data is cached rather than stored) |

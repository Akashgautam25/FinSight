# FinSight AI — REST API Reference

Interactive OpenAPI docs: **http://localhost:8000/docs** (Swagger) and `/redoc`.
Base path: `/api/v1`. All endpoints except auth and `/system/status` require `Authorization: Bearer <access_token>`.

## Authentication — `/auth`
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (creates starter portfolio + watchlist), returns tokens |
| POST | `/auth/login` | Email + password → access & refresh tokens |
| POST | `/auth/refresh` | Exchange refresh token for a new token pair |
| POST | `/auth/logout` | Client-side token discard |
| GET / PATCH | `/auth/me` | Current user profile / update name, bio, currency, timezone |
| GET / PUT | `/auth/me/preferences` | Theme, default market |
| POST | `/auth/change-password` | Requires current password |
| POST | `/auth/forgot-password` | Issues a single-use 30-min reset token (emailed, or returned as `dev_reset_link` in development without SMTP) |
| POST | `/auth/reset-password` | Token + new password |

## Stocks — `/stocks`
| Method | Path | Description |
|---|---|---|
| GET | `/stocks/search?q=` | Ticker / company search |
| GET | `/stocks/market/overview` | Indices, top gainers, losers, most active, market status |
| GET | `/stocks/quotes?symbols=A,B` | Batch quotes (one download call) |
| GET | `/stocks/compare?symbols=&period=` | Details, normalised performance, risk stats, correlation |
| GET | `/stocks/{symbol}` | Quote + fundamentals |
| GET | `/stocks/{symbol}/history?period=&interval=&indicators=` | OHLCV (+ SMA, Bollinger, RSI, MACD overlays) |
| GET | `/stocks/{symbol}/technical` | Latest indicators + interpreted signals |
| GET | `/stocks/{symbol}/fundamentals` | Fundamentals + description |

## News & sentiment — `/news`
| Method | Path | Description |
|---|---|---|
| GET | `/news?category=` | Market / sector headlines with sentiment (`technology`, `finance`, `healthcare`, `energy`, `consumer`, `india`) |
| GET | `/news/{symbol}` | Company news with sentiment |
| GET | `/news/{symbol}/sentiment` | Aggregated sentiment distribution |
| POST | `/news/sentiment/analyze` | Score arbitrary text |
| GET | `/news/sentiment/model` | Active sentiment model |

## Portfolios — `/portfolios`
| Method | Path | Description |
|---|---|---|
| GET / POST | `/portfolios` | List / create |
| GET / PATCH / DELETE | `/portfolios/{id}` | Read / rename / delete |
| GET / POST | `/portfolios/{id}/transactions` | Ledger / record BUY or SELL (validates symbol and prevents overselling) |
| DELETE | `/portfolios/{id}/transactions/{tx_id}` | Remove a transaction and rebuild holdings |
| GET | `/portfolios/{id}/holdings` | Positions with live prices and weights |
| GET | `/portfolios/{id}/analytics` | P&L, Sharpe, Sortino, volatility, drawdown, beta, VaR, CVaR, allocation, performance vs S&P 500 |

## Watchlists — `/watchlists`
`GET/POST /watchlists`, `PATCH/DELETE /watchlists/{id}`, `POST /watchlists/{id}/symbols`, `DELETE /watchlists/{id}/symbols/{symbol}`, `GET /watchlists/{id}/quotes`.

## ML predictions — `/predictions`
| Method | Path | Description |
|---|---|---|
| POST | `/predictions/train` | Queue background training `{symbol, model_types, lookback_years}` → 202 |
| GET | `/predictions/{symbol}/status` | `queued` / `running` (progress, message) / `completed` / `failed` / `not_trained` |
| GET | `/predictions/{symbol}` | Forecasts per model & horizon with 95 % intervals, best model, forecast path |
| GET | `/predictions/{symbol}/evaluation` | Validation/test metrics, naive baseline, splits, backtest series, feature importance |
| GET | `/predictions/trained` | Trained symbols + model availability |

## Optimization — `/optimization`
`POST /optimization/efficient-frontier` (full frontier, random portfolios, assets, correlation, allocations),
`POST /optimization/max-sharpe`, `POST /optimization/min-volatility`.
Body: `{symbols[], period, risk_free_rate, min_weight, max_weight, investment_amount?}` — infeasible inputs return 400.

## AI assistant & reports
| Method | Path | Description |
|---|---|---|
| POST | `/ai/chat/stream` | **SSE stream**: `session`, `status`, `tool` (running/done), `token`, `done` (sources, suggestions, provider) |
| POST | `/ai/chat` | Same agent, non-streaming: `{message, session_id?}` → answer, sources, tool calls, provider, suggestions |
| POST | `/ai/insight/stream` | **SSE stream** of an AI insight: `{kind: stock\|portfolio\|market\|predictions\|news, symbol?, refresh?}` |
| GET | `/ai/status`, `/ai/models` | Active LLM, available providers, installed Ollama models |
| PUT | `/ai/models` | Switch provider preference / local model `{provider?, ollama_model?}` |
| GET / DELETE | `/ai/sessions`, `/ai/sessions/{id}` | Chat history |
| POST | `/ai/generate-report` (alias `POST /reports`) | Build report + PDF |
| GET / DELETE | `/reports`, `/reports/{id}` | Saved reports |
| GET | `/reports/{id}/export` | PDF download |

## Alerts & notifications
`GET/POST /alerts`, `DELETE /alerts/{id}`, `POST /alerts/check` (evaluate now) ·
`GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`, `DELETE /notifications/{id}`.

## System
`GET /health`, `GET /api/v1/system/status` (database, cache, market-data source, sentiment model, LLM mode, ML model availability).

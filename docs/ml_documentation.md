# FinSight AI — Machine Learning & Quantitative Methods

## 1. Problem formulation
Supervised regression of the **forward h-day return** for h ∈ {1, 5, 10, 30} trading days:

r̂(t, h) = f_θ(x_t),   where r(t, h) = Close[t+h] / Close[t] − 1

The predicted price is Close[t] · (1 + r̂). Predicting returns rather than price levels matters: tree models
(Random Forest, XGBoost) cannot extrapolate beyond the range of prices seen in training, but returns are
stationary enough to be learned at any price level.

## 2. Features (32, all scale-invariant, `app/ml/feature_engineering.py`)
| Group | Features |
|---|---|
| Returns | daily return, log return, high–low range / close |
| Trend | close / SMA(5, 10, 20, 50, 200) − 1, SMA20/SMA50 − 1, SMA50/SMA200 − 1, EMA12/EMA26 − 1 |
| Oscillators | RSI(14, Wilder) / 100, MACD / close, signal / close, histogram / close, Bollinger width, %B |
| Volatility | 10- and 20-day return std, ATR(14) / close |
| Momentum | 5/10/20-day momentum, 5/10-day rate of change |
| Volume | volume / 20-day average, OBV 10-day slope (normalised) |
| Lags | returns lagged 1, 2, 3, 5, 10 days |

A unit test verifies that appending future rows never changes previously computed features (no look-ahead),
and another that multiplying all prices by 10 leaves every feature unchanged (scale invariance).

## 3. Leakage prevention
1. **Chronological split** — 70 % train, 15 % validation, 15 % test; no shuffling, no k-fold.
2. **Purge gap** — `h` rows are dropped after the train block and after the validation block, because the label of
   row t uses prices up to t+h; without the gap, the last training labels would overlap the validation period.
3. **Scalers** (StandardScaler) fitted on training data only.
4. **Model selection** on validation RMSE; reported metrics come from the untouched test set.
5. **LSTM windows** — a window ending on day t predicts day t's target in both training and inference; validation
   windows may look back into training *features* (which are known at that time) but never labels.

## 4. Models (`app/ml/models/__init__.py`)
| Model | Configuration | Rationale |
|---|---|---|
| Linear Regression | Ridge (α = 1) | Interpretable baseline; L2 handles collinear indicators |
| Random Forest | 300 trees, depth 6, min leaf 10, 50 % features | Non-linear, robust, feature importances |
| XGBoost | 600 rounds, η = 0.03, depth 3, subsample 0.8, early stopping (50) on validation | Strong tabular learner |
| LSTM (PyTorch) | 2 layers × 64 units, dropout 0.2, 20-day windows, Adam 1e-3, batch 64, ReduceLROnPlateau, early stopping (patience 12) | Sequential patterns |

All seeds are fixed (42). PyTorch runs single-threaded because, on macOS, PyTorch and XGBoost ship separate OpenMP
runtimes that can deadlock when both are loaded in one process (found and fixed during development).

## 5. Evaluation (`app/ml/evaluation.py`)
Computed on reconstructed prices on the test set:

* **MAE, MSE, RMSE** — price error in currency units
* **MAPE** — mean absolute percentage error
* **R² (price)** — inflated by price autocorrelation; reported for completeness
* **R² (returns)** — the honest R²: share of return variance explained (≈ 0 is normal)
* **Directional accuracy** — correct up/down calls relative to the forecast-day close (50 % = coin flip)
* **Skill vs naive** = 1 − RMSE_model / RMSE_naive, where the naive forecast is "price stays the same"

**Prediction intervals:** ±1.96 × std(validation residuals of returns), i.e. an empirical 95 % band.

### Expected results
Daily returns of liquid stocks are close to a random walk (weak-form market efficiency), so skill vs naive is
typically within a few percent of zero and directional accuracy near 50–55 %. On the deterministic simulated data
(a pure random walk) no model can beat the naive forecast — the test suite asserts this, which doubles as a
leakage check: a leaking pipeline would show suspiciously high skill. Present these results honestly — that
honesty is a strength of the project.

## 6. Pipeline & serving
`TrainingPipeline` (data → features → per-horizon split → train → evaluate → save) writes artifacts to
`backend/data/models/<SYMBOL>/h<h>/` and a `metadata.json` registry (metrics, splits, backtest series, feature
importances, hyperparameters). Runs are also recorded in the `ml_models` and `model_evaluations` tables. Training
takes ~10–60 s and runs in a background worker; `PredictionService` loads the artifacts and forecasts from the latest data.

## 7. Sentiment analysis (`app/services/sentiment_service.py`)
* **FinBERT** (ProsusAI/finbert, default) — downloaded once and loaded in a background thread at startup.
* **Lexicon model** otherwise — Loughran-McDonald-style finance word lists, multi-word phrase rules ("beats
  expectations", "cuts guidance"), negation handling within a 3-token window and intensity modifiers. Outputs
  calibrated positive/negative/neutral probabilities and a compound score in [−1, 1].

## 8. Portfolio mathematics (`app/services/portfolio_service.py`, `optimization_service.py`)
* Annualised return (geometric), volatility σ√252, Sharpe, Sortino (downside deviation), maximum drawdown,
  beta = Cov(r_p, r_m) / Var(r_m) against the S&P 500, 1-day 95 % historical VaR and CVaR.
* Markowitz optimisation: μ = historical CAGR, Σ = Ledoit-Wolf shrinkage; SLSQP for max-Sharpe, min-variance
  and target-return problems (efficient frontier); Dirichlet-sampled Monte Carlo portfolios; greedy whole-share allocation.

## 9. Generative AI (LLM) layer
* **Providers** (`app/ai/llm.py`): Ollama (local, native `/api/chat` with an 8k context window), and Gemini, Groq and OpenAI through
  OpenAI-compatible Chat Completions. All support streaming and function calling; failures fall through to the next provider.
* **Agent** (`app/ai/agent.py`): deterministic retrieval for reliability with small local models, plus LLM-initiated tool calls,
  a grounding system prompt with an interpretation guide (P/E, RSI, beta, Sharpe thresholds) and an enforced disclaimer.
* **Insights** (`app/ai/insights.py`): task-specific prompts over freshly gathered data, streamed and cached for 15 minutes.
* **Embeddings**: `nomic-embed-text` (768-d) with task prefixes (`search_document:` / `search_query:`); hybrid score
  0.65·cosine + 0.35·TF-IDF.
* **Model choice on 8 GB laptops**: `qwen2.5:3b` writes better analysis (~9 tok/s on an M3 under memory pressure);
  `qwen2.5:1.5b` is ~2× faster. Both are selectable in Settings.

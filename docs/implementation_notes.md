# Implementation Notes — what is actually built

Use this when updating the project report so every claim matches the code.

| Topic | Implementation in this repository | Report wording to revisit |
|---|---|---|
| Background jobs | asyncio task + worker thread with progress tracking (`app/ml/jobs.py`); periodic asyncio loop for alerts | "Celery" workers |
| AI assistant | Custom agent (`app/ai/agent.py`): deterministic planner fetches verified data with 8 tools, then the LLM answers and may call further tools via **native function calling** (OpenAI-compatible / Ollama), streamed over SSE. LLM layer: `app/ai/llm.py` (Ollama local, Gemini, Groq, OpenAI) | "LangGraph-orchestrated", LangChain |
| Generative insights | `app/ai/insights.py`: AI analyst notes, portfolio reviews, market briefings, news digests, ML explanations (streamed, cached 15 min) | (new — worth adding to the report) |
| Retrieval (RAG) | Hybrid: `nomic-embed-text` embeddings via Ollama (in-memory vector index, cosine similarity) + TF-IDF, weights 0.65/0.35 (`app/ai/knowledge_base.py`) | ChromaDB, all-MiniLM-L6-v2 embeddings, pgvector |
| LLM | Local Qwen 2.5 (3B, 1.5B) via Ollama by default; Gemini / Groq / OpenAI when a key is set | "Google Gemini" only |
| Portfolio optimisation | NumPy/SciPy SLSQP + scikit-learn Ledoit-Wolf, implemented from first principles | PyPortfolioOpt |
| Sentiment | FinBERT (default, loaded in the background), finance-specific lexicon model as fallback | matches |
| Databases | SQLite by default, PostgreSQL 16 in Docker; in-memory cache or Redis | PostgreSQL + pgvector + Redis + ChromaDB required |
| Market data | Yahoo Finance via yfinance (no key) + deterministic simulated fallback; Finnhub/NewsAPI optional | Alpha Vantage / FMP |
| Forecast target | Forward h-day **return**, converted to price | price level |
| Scaling | StandardScaler fitted on training data | MinMaxScaler |
| Validation | Single chronological 70/15/15 split with purge gap | "walk-forward validation" |
| LSTM | 2 × 64 units, dropout 0.2, 20-day windows | 2 × 128 units |
| Results | Measured per run and shown in the app (test-set metrics + naive baseline). Typical skill vs naive ≈ 0 | "XGBoost and LSTM achieved superior directional accuracy" — replace with your measured numbers from the Predictions page |

## Bugs found and fixed while making the project run
* App crashed on import (`Annotated` dependency combined with `= Depends()`); JSONB broke SQLite; passlib incompatible with bcrypt 5; missing `greenlet`; invalid npm packages and Next.js config.
* LSTM never trained successfully: prediction length did not match targets (and windows were misaligned between training and inference).
* PyTorch + XGBoost OpenMP deadlock on macOS (fixed by single-threaded torch).
* Training ran on the event loop and froze the API; now a background worker with progress.
* `Decimal * float` errors in portfolio maths; deleting a portfolio with holdings violated foreign keys; overselling was allowed.
* PDF export link was unauthenticated; watchlists/settings were mock UIs; alerts were never evaluated.
* PyTorch (FinBERT) loaded before XGBoost made XGBoost segfault on macOS (two OpenMP runtimes) — XGBoost is now imported first at startup.
* An open browser tab after a frontend rebuild showed "Application error: a client-side exception has occurred" (missing JS chunks) — error boundaries now show a friendly message and reload automatically.

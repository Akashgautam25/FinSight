# FinSight AI 🧠📈

> **AI-Powered Financial Intelligence & Stock Research Platform**
> B.Tech Final-Year Project | Computer Science & Artificial Intelligence

FinSight AI is a production-quality financial intelligence platform combining full-stack web development, machine learning, NLP sentiment analysis, quantitative portfolio optimization, and generative AI into one integrated application.

---

## ✨ Features

- 📊 **Market Dashboard** — Indices, gainers/losers, sector performance, market overview
- 🔍 **Stock Explorer** — Search, filter, and deep-dive any publicly traded company
- 📈 **Interactive Charts** — Candlestick, OHLCV, technical indicators (RSI, MACD, Bollinger Bands)
- 🤖 **ML Price Predictions** — Linear Regression, Random Forest, XGBoost, LSTM models
- 📰 **News & Sentiment** — FinBERT-powered financial news sentiment analysis
- 💬 **AI Research Assistant** — LangGraph agent with RAG, tool calling, source citations
- 💼 **Portfolio Manager** — Multi-portfolio tracking, P&L, analytics, risk metrics
- 📐 **Portfolio Optimizer** — Modern Portfolio Theory, efficient frontier, max Sharpe
- ⚖️ **Stock Comparison** — Compare up to 5 stocks across all metrics
- 📋 **Research Reports** — AI-generated PDF reports with executive summaries
- 🔔 **Price Alerts** — Custom price and % change alerts with notifications
- 👤 **Authentication** — JWT-based auth with refresh tokens, secure password hashing

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic |
| Database | PostgreSQL 16 (pgvector), Redis 7, ChromaDB |
| ML/AI | PyTorch, XGBoost, scikit-learn, Hugging Face, LangChain |
| Infrastructure | Docker, Celery, Nginx |

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/finsight-ai.git
cd finsight-ai
```

### 2. Configure environment variables
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Run with Docker Compose
```bash
docker-compose up --build
```

### 4. Access the application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## 🔑 Required API Keys

| Service | Purpose | Link |
|---|---|---|
| Alpha Vantage | Stock quotes & technicals | [Get key](https://www.alphavantage.co/support/#api-key) |
| Financial Modeling Prep | Fundamentals & ratios | [Get key](https://financialmodelingprep.com/developer/docs/) |
| Finnhub | Real-time data & news | [Get key](https://finnhub.io/register) |
| NewsAPI | Financial news | [Get key](https://newsapi.org/register) |
| Google Gemini | AI assistant LLM | [Get key](https://aistudio.google.com/app/apikey) |

---

## 📁 Project Structure

```
finsight-ai/
├── frontend/          # Next.js 14 application
├── backend/           # FastAPI Python backend
├── ml_research/       # Jupyter notebooks for ML experiments
├── docs/              # Architecture & project documentation
└── infrastructure/    # Docker, Nginx, scripts
```

---

## ⚠️ Disclaimer

FinSight AI is an **educational research tool** and does **not** constitute financial advice. All predictions are model estimates with inherent uncertainty. Never make investment decisions based solely on this platform.

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.

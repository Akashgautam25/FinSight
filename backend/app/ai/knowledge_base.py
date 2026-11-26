"""
FinSight AI — Financial Knowledge Base (retrieval for the AI assistant)

A curated corpus of financial concepts used for retrieval-augmented generation (RAG).

Retrieval is hybrid:
  * Dense semantic search — documents and queries are embedded with the local
    `nomic-embed-text` model (via Ollama) and ranked by cosine similarity, so
    "is the stock expensive?" finds the P/E entry even without shared words.
  * Sparse lexical search — TF-IDF (unigrams + bigrams, sublinear TF).
  Final score = 0.65 · dense + 0.35 · sparse. Without an embedding model the
  search falls back to TF-IDF alone.
"""

from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOCUMENTS = [
    ("P/E ratio (price-to-earnings)", "valuation pe ratio price earnings multiple expensive cheap",
     "The P/E ratio divides the share price by earnings per share (EPS). It shows how much investors pay for each unit of profit. "
     "A high P/E (e.g. above 25–30) usually signals expectations of strong future growth or an expensive stock; a low P/E (below ~15) can mean "
     "undervaluation or weak growth prospects. Compare P/E within the same industry, because normal levels differ by sector, and remember it "
     "is meaningless when earnings are negative."),
    ("EPS (earnings per share)", "eps earnings per share profit net income",
     "EPS is net income divided by the number of shares outstanding. Rising EPS over time indicates growing profitability per share. "
     "Trailing EPS uses the last 12 months of reported results; forward EPS uses analyst estimates."),
    ("Market capitalization", "market cap size large cap small cap company value",
     "Market cap is share price × shares outstanding — the market value of a company's equity. Large caps (> $10B) are typically more stable; "
     "small caps (< $2B) can grow faster but are more volatile and less liquid."),
    ("Beta", "beta market risk systematic volatility sensitivity",
     "Beta measures how much a stock moves relative to the overall market (usually the S&P 500). Beta = 1 moves with the market, beta > 1 "
     "amplifies market moves (more volatile), beta < 1 is more defensive. It is estimated as Cov(stock, market) / Var(market) from historical returns."),
    ("Dividend yield", "dividend yield income payout",
     "Dividend yield is annual dividends per share divided by the share price. It shows the cash income return from holding a stock. "
     "A very high yield can be a warning sign if the price has fallen because the dividend may be cut."),
    ("Return on equity (ROE)", "roe return on equity profitability efficiency",
     "ROE = net income / shareholders' equity. It measures how efficiently management turns shareholder capital into profit. "
     "Consistently high ROE (> 15%) is attractive, but very high ROE can also come from heavy debt or share buybacks shrinking equity."),
    ("Return on assets (ROA)", "roa return on assets",
     "ROA = net income / total assets. It shows how profitably a company uses everything it owns, and is useful for comparing capital-intensive businesses."),
    ("Debt-to-equity ratio", "debt to equity leverage balance sheet solvency",
     "Debt-to-equity divides total debt by shareholders' equity. Higher values mean more financial leverage — boosting returns in good times but "
     "increasing risk when earnings fall or interest rates rise. Acceptable levels vary by industry (banks and utilities run higher)."),
    ("Profit margin", "profit margin net margin profitability",
     "Net profit margin = net income / revenue. It shows how much of each unit of sales becomes profit. Software firms often have margins above 25%, "
     "while retailers operate on low single digits."),
    ("Free cash flow", "free cash flow fcf cash generation",
     "Free cash flow is operating cash flow minus capital expenditure — the cash a business generates that can fund dividends, buybacks, "
     "debt repayment or growth. Many analysts consider it harder to manipulate than accounting earnings."),
    ("RSI (Relative Strength Index)", "rsi relative strength index overbought oversold momentum oscillator",
     "RSI is a momentum oscillator from 0 to 100 computed from the average gains and losses over 14 periods (Wilder's smoothing). "
     "Readings above 70 suggest a stock may be overbought; below 30 may be oversold. In strong trends RSI can stay extreme for a long time, "
     "so it works best combined with trend indicators."),
    ("MACD", "macd moving average convergence divergence signal line histogram momentum",
     "MACD is the 12-day EMA minus the 26-day EMA; its 9-day EMA is the signal line. MACD crossing above the signal line indicates improving "
     "momentum (bullish), crossing below indicates weakening momentum (bearish). The histogram shows the gap between the two lines."),
    ("Bollinger Bands", "bollinger bands volatility standard deviation squeeze",
     "Bollinger Bands are a 20-day moving average with bands two standard deviations above and below. Prices near the upper band are stretched "
     "upward, near the lower band stretched downward. Narrowing bands (a squeeze) indicate low volatility that often precedes a big move."),
    ("Moving averages (SMA/EMA)", "moving average sma ema trend 50 day 200 day golden cross death cross",
     "A simple moving average (SMA) is the average closing price over N days; an exponential moving average (EMA) weights recent prices more. "
     "Price above the 50- or 200-day average indicates an uptrend. A golden cross (50-day crossing above 200-day) is read as bullish, "
     "a death cross (crossing below) as bearish."),
    ("ATR (Average True Range)", "atr average true range volatility stop loss",
     "ATR measures average daily price range including gaps. Traders use it to size positions and set stop-losses proportional to a stock's typical movement."),
    ("Volatility", "volatility standard deviation risk annualized",
     "Volatility is the standard deviation of returns, usually annualized by multiplying daily volatility by √252. Higher volatility means larger "
     "price swings in both directions and therefore higher risk."),
    ("Sharpe ratio", "sharpe ratio risk adjusted return",
     "The Sharpe ratio is (portfolio return − risk-free rate) / volatility. It measures return earned per unit of total risk. Above 1 is "
     "generally good, above 2 very good. It assumes returns are roughly normally distributed."),
    ("Sortino ratio", "sortino ratio downside deviation risk adjusted",
     "The Sortino ratio is like the Sharpe ratio but divides excess return by downside deviation only, so upside volatility is not penalised. "
     "It is preferred when return distributions are skewed."),
    ("Maximum drawdown", "max drawdown peak trough loss",
     "Maximum drawdown is the largest peak-to-trough fall in portfolio value over a period. It describes the worst loss an investor would have "
     "experienced and how painful a strategy can be to hold."),
    ("Value at Risk (VaR) and CVaR", "var value at risk cvar expected shortfall tail risk",
     "1-day 95% Value at Risk is the loss that should only be exceeded on 5% of days. Conditional VaR (expected shortfall) is the average loss "
     "on those worst 5% of days, so it captures tail risk better. FinSight estimates both by historical simulation."),
    ("Diversification", "diversification correlation concentration risk portfolio",
     "Diversification combines assets that do not move perfectly together, so losses in one can be offset by others. The benefit depends on "
     "correlation: low or negative correlations reduce portfolio volatility. Concentrating more than ~20–30% in one stock or sector raises risk."),
    ("Modern Portfolio Theory & efficient frontier", "modern portfolio theory markowitz efficient frontier optimization max sharpe minimum variance",
     "Modern Portfolio Theory (Markowitz, 1952) chooses weights that maximise expected return for a given level of risk. The efficient frontier "
     "is the set of portfolios with the highest return for each volatility. The maximum-Sharpe portfolio is where a line from the risk-free rate "
     "touches the frontier; the minimum-variance portfolio has the lowest risk. Results depend heavily on estimated inputs, which are noisy."),
    ("Correlation", "correlation coefficient relationship assets",
     "Correlation (−1 to +1) measures how two assets' returns move together. +1 means they move in lockstep, 0 means unrelated, −1 opposite. "
     "Correlations often rise during market crashes, reducing diversification exactly when it is needed."),
    ("Stock price prediction models", "prediction forecast machine learning model linear regression random forest xgboost lstm",
     "FinSight trains four models per stock: ridge linear regression (baseline), random forest, XGBoost (gradient boosting) and an LSTM neural "
     "network. They predict the forward return for 1, 5, 10 and 30 trading days from technical features, using a chronological train/validation/test "
     "split with a purge gap to prevent leakage. Daily returns are close to a random walk, so even good models beat a naive 'no change' forecast "
     "only slightly — predictions are uncertain estimates, not signals."),
    ("Directional accuracy", "directional accuracy hit rate up down",
     "Directional accuracy is the share of forecasts that get the direction (up or down) right. 50% is coin-flip level; consistently above "
     "~55% on unseen data is considered meaningful for daily stock returns."),
    ("Data leakage and overfitting", "leakage overfitting look ahead bias backtest",
     "Look-ahead bias happens when a model uses information that would not have been available at prediction time, producing unrealistically good "
     "backtests. FinSight avoids it by computing features only from past data, fitting scalers on training data only, splitting chronologically "
     "and purging rows at split boundaries."),
    ("News sentiment analysis (FinBERT)", "sentiment analysis finbert nlp news positive negative",
     "Sentiment analysis classifies news as positive, negative or neutral. FinBERT is a BERT language model fine-tuned on financial text, so it "
     "understands domain terms (e.g. 'liability' or 'volatile' are negative in finance). FinSight falls back to a finance-specific lexicon model "
     "when FinBERT is not installed. Sentiment is one input among many — markets often price news in quickly."),
    ("Bull and bear markets", "bull market bear market correction",
     "A bull market is a sustained rise in prices; a bear market is a decline of 20% or more from a recent peak. A correction is a 10–20% fall."),
    ("ETFs and index funds", "etf index fund passive investing s&p 500 nifty",
     "Exchange-traded funds and index funds hold baskets of securities that track an index such as the S&P 500 or NIFTY 50. They offer instant "
     "diversification at low cost and are the core of most long-term passive portfolios."),
    ("Dollar-cost averaging", "dollar cost averaging sip systematic investment",
     "Dollar-cost averaging (a SIP in India) invests a fixed amount at regular intervals regardless of price, buying more units when prices are "
     "low and fewer when high. It reduces timing risk and the emotional pressure of choosing an entry point."),
]


@lru_cache(maxsize=1)
def _index():
    texts = [f"{title} {keywords} {body}" for title, keywords, body in DOCUMENTS]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def retrieve(query: str, k: int = 2, min_score: float = 0.12) -> List[dict]:
    vectorizer, matrix = _index()
    scores = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
    ranked = scores.argsort()[::-1][:k]
    return [
        {"title": DOCUMENTS[i][0], "content": DOCUMENTS[i][2], "score": round(float(scores[i]), 3)}
        for i in ranked if scores[i] >= min_score
    ]


_dense_index: Dict[str, Optional[np.ndarray]] = {}


async def _doc_embeddings() -> Optional[np.ndarray]:
    from app.ai import llm
    from app.config import settings

    model = settings.ollama_embed_model
    if model in _dense_index and _dense_index[model] is not None:
        return _dense_index[model]
    vectors = await llm.embed([f"search_document: {t}. {k}. {b}" for t, k, b in DOCUMENTS])
    if not vectors:
        return None
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
    _dense_index[model] = matrix
    return matrix


async def aretrieve(query: str, k: int = 2, min_score: float = 0.4) -> List[dict]:
    """Hybrid semantic + lexical retrieval (falls back to TF-IDF only)."""
    from app.ai import llm

    if not query.strip():
        return []
    vectorizer, matrix = _index()
    sparse = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
    docs = await _doc_embeddings()
    q = await llm.embed([f"search_query: {query}"]) if docs is not None else None
    if docs is None or not q:
        return [dict(d, method="tfidf") for d in retrieve(query, k)]
    qv = np.asarray(q[0], dtype=np.float32)
    qv /= np.linalg.norm(qv) + 1e-9
    dense = docs @ qv
    score = 0.65 * dense + 0.35 * sparse
    ranked = score.argsort()[::-1][:k]
    top = float(score[ranked[0]])
    return [
        {"title": DOCUMENTS[i][0], "content": DOCUMENTS[i][2], "score": round(float(score[i]), 3), "method": "semantic+tfidf"}
        for i in ranked if score[i] >= min_score and score[i] >= 0.85 * top
    ]

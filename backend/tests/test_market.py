async def test_stock_detail(auth_client):
    r = await auth_client.get("/api/v1/stocks/AAPL")
    d = r.json()
    assert r.status_code == 200 and d["is_demo"] is True
    assert d["metrics"]["pe_ratio"] > 0
    assert d["change_pct"] is not None


async def test_unknown_stock_404(auth_client):
    assert (await auth_client.get("/api/v1/stocks/NOTREAL")).status_code == 404


async def test_history_with_indicators(auth_client):
    d = (await auth_client.get("/api/v1/stocks/MSFT/history", params={"period": "6mo", "indicators": True})).json()
    assert d["data_points"] > 100
    last = d["data"][-1]
    assert last["sma_200"] is not None and 0 <= last["rsi_14"] <= 100


async def test_technical_indicators(auth_client):
    t = (await auth_client.get("/api/v1/stocks/NVDA/technical")).json()
    assert 0 <= t["rsi_14"] <= 100
    assert t["bb_lower"] < t["bb_middle"] < t["bb_upper"]
    assert t["overall_signal"] in {"bullish", "bearish", "neutral"} and t["signals"]


async def test_market_overview(auth_client):
    o = (await auth_client.get("/api/v1/stocks/market/overview")).json()
    assert len(o["indices"]) == 5
    assert all(m["change_pct"] > 0 for m in o["top_gainers"])
    assert all(m["change_pct"] < 0 for m in o["top_losers"])


async def test_search(auth_client):
    r = (await auth_client.get("/api/v1/stocks/search", params={"q": "micro"})).json()
    assert any(x["symbol"] == "MSFT" for x in r)


async def test_compare(auth_client):
    c = (await auth_client.get("/api/v1/stocks/compare", params={"symbols": "AAPL,MSFT,KO"})).json()
    assert len(c["performance"]) > 50 and c["performance"][0]["AAPL"] == 0
    assert c["comparison"]["KO"]["stats"]["volatility_pct"] > 0


def test_rsi_bounds_and_definition():
    import numpy as np
    import pandas as pd

    from app.ml.indicators import rsi

    up = pd.Series(np.arange(1, 50, dtype=float))
    assert rsi(up).iloc[-1] == 100  # only gains → RSI 100
    noisy = pd.Series(100 + np.random.default_rng(0).normal(0, 1, 300).cumsum())
    values = rsi(noisy).dropna()
    assert ((values >= 0) & (values <= 100)).all()

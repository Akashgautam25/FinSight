from app.ai.agent import FinSightAgent
from app.ai.knowledge_base import retrieve


async def test_symbol_extraction():
    agent = FinSightAgent()
    assert await agent.extract_symbols("How is Apple doing vs Microsoft?") == ["AAPL", "MSFT"]
    assert await agent.extract_symbols("Is NVDA overbought? What is the RSI?") == ["NVDA"]
    assert await agent.extract_symbols("What is the P/E ratio and EPS?") == []
    assert await agent.extract_symbols("tell me about reliance") == ["RELIANCE.NS"]


def test_intents():
    assert "compare" in FinSightAgent.detect_intents("compare AAPL vs MSFT", ["AAPL", "MSFT"])
    assert "education" in FinSightAgent.detect_intents("What is the Sharpe ratio?", [])
    assert "prediction" in FinSightAgent.detect_intents("forecast TSLA next week", ["TSLA"])
    assert "portfolio" in FinSightAgent.detect_intents("analyse my portfolio risk", [])


def test_knowledge_retrieval():
    top = retrieve("what does a high price to earnings ratio mean", k=1)
    assert top and "P/E" in top[0]["title"]


async def test_chat_offline_mode(auth_client):
    r = (await auth_client.post("/api/v1/ai/chat", json={"message": "How is AAPL doing?"})).json()
    assert r["llm_provider"] == "offline"
    assert "Apple" in r["content"] and "not financial advice" in r["content"]
    assert any(s["type"] == "market_data" for s in r["sources"])
    follow = (await auth_client.post("/api/v1/ai/chat", json={"message": "and its RSI?", "session_id": r["session_id"]})).json()
    assert any("AAPL" in t for t in follow["tool_calls_made"])
    msgs = (await auth_client.get(f"/api/v1/ai/sessions/{r['session_id']}")).json()
    assert len(msgs) == 4


async def test_watchlist_crud(auth_client):
    wl = (await auth_client.get("/api/v1/watchlists")).json()[0]
    assert (await auth_client.post(f"/api/v1/watchlists/{wl['id']}/symbols", json={"symbol": "ko"})).status_code == 201
    assert (await auth_client.post(f"/api/v1/watchlists/{wl['id']}/symbols", json={"symbol": "KO"})).status_code == 409
    quotes = (await auth_client.get(f"/api/v1/watchlists/{wl['id']}/quotes")).json()
    assert any(i["symbol"] == "KO" and i["price"] for i in quotes["items"])
    assert (await auth_client.delete(f"/api/v1/watchlists/{wl['id']}/symbols/KO")).status_code == 204


async def test_alert_triggers_notification(auth_client):
    r = await auth_client.post("/api/v1/alerts", json={"symbol": "AAPL", "alert_type": "price_above", "target_value": 1})
    assert r.status_code == 201
    assert (await auth_client.post("/api/v1/alerts/check")).json()["triggered"] == 1
    alerts = (await auth_client.get("/api/v1/alerts")).json()
    assert alerts[0]["is_triggered"]
    notes = (await auth_client.get("/api/v1/notifications")).json()
    assert notes["unread_count"] >= 1 and notes["items"][0]["type"] == "price_alert"


async def test_report_generation_and_pdf(auth_client):
    rep = (await auth_client.post("/api/v1/ai/generate-report", json={"symbol": "MSFT"})).json()
    assert rep["status"] == "ready" and rep["report_data"]["executive_summary"]
    pdf = await auth_client.get(f"/api/v1/reports/{rep['id']}/export")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert (await auth_client.delete(f"/api/v1/reports/{rep['id']}")).status_code == 204


async def test_system_status(client):
    s = (await client.get("/api/v1/system/status")).json()
    assert s["database"] == "sqlite" and s["market_data"]["mode"] == "demo"

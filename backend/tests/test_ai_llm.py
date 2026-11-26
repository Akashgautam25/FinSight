"""LLM agent loop, streaming endpoints and provider handling (with a fake LLM — no network)."""
import json

from app.ai import llm
from app.ai.agent import FinSightAgent

FAKE = llm.Provider("fake", "test-model", "http://fake")


def _fake_stream(answer: str, tool: str = "get_market_overview"):
    """First call asks for a tool; once a tool result is in the conversation, it answers."""
    calls = []

    async def stream_chat(provider, messages, tools=None, temperature=0.2, max_tokens=1200):
        calls.append({"tools": bool(tools), "n_messages": len(messages)})
        if tools and not any(m["role"] == "tool" for m in messages):
            yield {"type": "tool_calls", "calls": [{"id": "c1", "name": tool, "arguments": {}}]}
            return
        for word in answer.split(" "):
            yield {"type": "token", "text": word + " "}
        yield {"type": "end"}

    return stream_chat, calls


async def test_agent_executes_model_requested_tool_and_streams(monkeypatch):
    stream_chat, calls = _fake_stream("The market is mixed today.")
    monkeypatch.setattr(llm, "stream_chat", stream_chat)

    async def providers():
        return [FAKE]
    monkeypatch.setattr(llm, "available_providers", providers)

    events = [e async for e in FinSightAgent().stream("Give me a quick update")]
    model_tools = [e for e in events if e["type"] == "tool" and e.get("by_model")]
    assert [e["status"] for e in model_tools] == ["running", "done"]
    assert model_tools[0]["name"] == "get_market_overview"
    done = events[-1]
    assert done["type"] == "done" and done["llm_provider"] == "fake:test-model"
    assert done["content"].startswith("The market is mixed today.")
    assert "not financial advice" in done["content"]  # disclaimer appended when the model omits it
    assert any(s["type"] == "market_data" for s in done["sources"])
    assert len(calls) == 2  # tool round + answer round


async def test_agent_falls_back_to_next_provider(monkeypatch):
    async def stream_chat(provider, messages, tools=None, **kw):
        if provider.name == "broken":
            raise llm.LLMError("boom")
            yield  # pragma: no cover
        yield {"type": "token", "text": "Answer from backup."}
        yield {"type": "end"}

    async def providers():
        return [llm.Provider("broken", "x", "http://x"), FAKE]
    monkeypatch.setattr(llm, "stream_chat", stream_chat)
    monkeypatch.setattr(llm, "available_providers", providers)
    result = await FinSightAgent().run("What is the Sharpe ratio?")
    assert result["llm_provider"] == "fake:test-model"
    assert result["content"].startswith("Answer from backup.")


async def test_agent_offline_when_no_provider():
    result = await FinSightAgent().run("What is diversification?")
    assert result["llm_provider"] == "offline" and "Diversification" in result["content"]


def _parse_sse(text: str):
    return [json.loads(line[5:]) for line in text.splitlines() if line.startswith("data:")]


async def test_chat_stream_endpoint_persists_history(auth_client):
    resp = await auth_client.post("/api/v1/ai/chat/stream", json={"message": "How is AAPL doing?"})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "session" and types[-1] == "done"
    assert "tool" in types and "token" in types
    done = events[-1]
    assert "Apple" in done["content"] and done["message_id"]
    history = (await auth_client.get(f"/api/v1/ai/sessions/{done['session_id']}")).json()
    assert [m["role"] for m in history] == ["user", "assistant"]


async def test_insight_stream_and_cache(auth_client):
    body = {"kind": "stock", "symbol": "MSFT"}
    first = _parse_sse((await auth_client.post("/api/v1/ai/insight/stream", json=body)).text)
    assert first[-1]["type"] == "done" and first[-1]["cached"] is False
    text = "".join(e["text"] for e in first if e["type"] == "token")
    assert "Microsoft" in text
    second = _parse_sse((await auth_client.post("/api/v1/ai/insight/stream", json=body)).text)
    assert second[-1]["cached"] is True


async def test_insight_kinds(auth_client):
    for body in ({"kind": "market"}, {"kind": "portfolio"}, {"kind": "news"}, {"kind": "predictions", "symbol": "KO"}):
        events = _parse_sse((await auth_client.post("/api/v1/ai/insight/stream", json=body)).text)
        assert events[-1]["type"] == "done", (body, events[-1])
    bad = await auth_client.post("/api/v1/ai/insight/stream", json={"kind": "stock"})
    assert bad.status_code == 422


async def test_model_status_and_selection(auth_client):
    status = (await auth_client.get("/api/v1/ai/models")).json()
    assert status["mode"] == "offline_analyst" and status["ollama"]["reachable"] is False
    bad = await auth_client.put("/api/v1/ai/models", json={"ollama_model": "not-installed:1b"})
    assert bad.status_code == 400


def test_message_conversion_roundtrip():
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "get_market_overview", "arguments": {"a": 1}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "get_market_overview", "content": "data"},
    ]
    oa = llm._to_openai(msgs)
    assert oa[1]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}' and oa[2]["tool_call_id"] == "c1"
    ol = llm._to_ollama(msgs)
    assert ol[1]["tool_calls"][0]["function"]["arguments"] == {"a": 1} and ol[2]["tool_name"] == "get_market_overview"

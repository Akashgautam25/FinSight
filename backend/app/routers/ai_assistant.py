"""
FinSight AI — AI Assistant Router

Streaming endpoints use Server-Sent Events (text/event-stream). Each event is a
JSON object on a `data:` line:

    {"type": "session", "session_id"}                      (chat only, first event)
    {"type": "status", "message"}                          progress text
    {"type": "tool", "id", "name", "args", "status", ...}  tool call started / finished
    {"type": "token", "text"}                              answer text delta
    {"type": "done", ...}                                  sources, suggestions, provider
    {"type": "error", "message"}
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai import llm
from app.ai.agent import FinSightAgent
from app.ai.insights import KINDS, stream_insight
from app.database import AsyncSessionLocal
from app.dependencies import CurrentUser, DBSession
from app.models import ChatMessage, ChatSession
from app.schemas.ai import ChatRequest, ChatResponse, GenerateReportRequest
from app.services.report_service import ReportService

router = APIRouter()
logger = logging.getLogger("finsight.ai.router")

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


class InsightRequest(BaseModel):
    kind: Literal["stock", "portfolio", "market", "predictions", "news"]
    symbol: Optional[str] = Field(None, max_length=20)
    refresh: bool = False


class ModelSelection(BaseModel):
    provider: Optional[Literal["auto", "gemini", "groq", "openai", "ollama", "offline"]] = None
    ollama_model: Optional[str] = Field(None, max_length=100)


# ── Status & model selection ─────────────────────────────────────────────────

@router.get("/status")
async def assistant_status(_: CurrentUser):
    return await llm.status()


@router.get("/models")
async def list_models(_: CurrentUser):
    return await llm.status()


@router.put("/models")
async def select_model(payload: ModelSelection, _: CurrentUser):
    if payload.ollama_model:
        models = await llm.ollama_models(force=True) or []
        if payload.ollama_model not in models and f"{payload.ollama_model}:latest" not in models:
            raise HTTPException(status_code=400, detail=f"Ollama model '{payload.ollama_model}' is not installed. Run: ollama pull {payload.ollama_model}")
    llm.save_runtime_settings(provider=payload.provider, ollama_model=payload.ollama_model)
    if payload.ollama_model:
        import asyncio
        asyncio.create_task(llm.warm_up())  # load the newly selected model in the background
    return await llm.status()


# ── Chat ─────────────────────────────────────────────────────────────────────

async def _session_and_history(user_id: str, session_id: Optional[str], first_message: str):
    async with AsyncSessionLocal() as db:
        if session_id:
            session = (await db.execute(
                select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            )).scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            rows = (await db.execute(
                select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.desc()).limit(8)
            )).scalars().all()
            return session.id, [{"role": m.role, "content": m.content} for m in reversed(rows)]
        title = first_message.strip().replace("\n", " ")
        session = ChatSession(id=str(uuid.uuid4()), user_id=user_id, title=title[:60] + ("…" if len(title) > 60 else ""))
        db.add(session)
        await db.commit()
        return session.id, []


async def _save_exchange(session_id: str, question: str, result: dict) -> str:
    message_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        db.add(ChatMessage(id=str(uuid.uuid4()), session_id=session_id, role="user", content=question, created_at=now))
        db.add(ChatMessage(id=message_id, session_id=session_id, role="assistant", content=result.get("content", ""),
                           sources=result.get("sources", []), tool_calls=result.get("tool_calls", []),
                           created_at=datetime.now(timezone.utc)))
        session = await db.get(ChatSession, session_id)
        if session:
            session.updated_at = datetime.now(timezone.utc)
        await db.commit()
    return message_id


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, current_user: CurrentUser):
    """Streaming chat: agent steps, tool calls and answer tokens as Server-Sent Events."""
    session_id, history = await _session_and_history(current_user.id, payload.session_id, payload.message)
    user_id = current_user.id

    async def events() -> AsyncIterator[str]:
        yield _sse({"type": "session", "session_id": session_id})
        try:
            async for event in FinSightAgent(user_id=user_id).stream(payload.message, history):
                if event["type"] == "done":
                    event["message_id"] = await _save_exchange(session_id, payload.message, event)
                    event["session_id"] = session_id
                yield _sse(event)
        except Exception as exc:
            logger.exception("Chat stream failed")
            yield _sse({"type": "error", "message": f"The assistant hit an error: {exc}"})

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, current_user: CurrentUser):
    """Non-streaming chat (same agent; returns the final answer only)."""
    session_id, history = await _session_and_history(current_user.id, payload.session_id, payload.message)
    result = await FinSightAgent(user_id=current_user.id).run(payload.message, history)
    message_id = await _save_exchange(session_id, payload.message, result)
    return ChatResponse(
        session_id=session_id, message_id=message_id, content=result["content"], sources=result["sources"],
        tool_calls_made=result["tool_calls"], llm_provider=result["llm_provider"], suggestions=result["suggestions"],
    )


# ── Insights ─────────────────────────────────────────────────────────────────

@router.post("/insight/stream")
async def insight_stream(payload: InsightRequest, current_user: CurrentUser):
    if payload.kind in ("stock", "predictions") and not payload.symbol:
        raise HTTPException(status_code=422, detail="symbol is required for this insight")
    assert payload.kind in KINDS
    user_id = current_user.id

    async def events() -> AsyncIterator[str]:
        try:
            async for event in stream_insight(payload.kind, payload.symbol, user_id, payload.refresh):
                yield _sse(event)
        except Exception as exc:
            logger.exception("Insight stream failed")
            yield _sse({"type": "error", "message": f"Could not generate the insight: {exc}"})

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


# ── Sessions & reports ───────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(current_user: CurrentUser, db: DBSession):
    rows = (await db.execute(
        select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.updated_at.desc()).limit(50)
    )).scalars().all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at, "updated_at": s.updated_at} for s in rows]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: CurrentUser, db: DBSession):
    session = (await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )).scalars().all()
    return [{"id": m.id, "role": m.role, "content": m.content, "sources": m.sources or [], "tool_calls": m.tool_calls or [],
             "created_at": m.created_at} for m in rows]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, current_user: CurrentUser, db: DBSession):
    session = (await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()


@router.post("/generate-report")
async def generate_report(payload: GenerateReportRequest, current_user: CurrentUser, db: DBSession):
    return await ReportService(db).generate(payload, current_user.id)

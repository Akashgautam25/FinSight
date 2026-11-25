"""
FinSight AI — AI Assistant Router
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models import ChatSession, ChatMessage
from app.schemas.ai import ChatRequest, ChatResponse, GenerateReportRequest
from app.ai.agent import FinSightAgent

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, current_user: CurrentUser, db: DBSession):
    # Get or create session
    session_id = payload.session_id
    if not session_id:
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            title=payload.message[:60],
        )
        db.add(session)
        await db.flush()
        session_id = session.id
    else:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Session not found")

    # Store user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)

    # Run AI agent
    agent = FinSightAgent()
    response = await agent.run(payload.message, session_id=session_id, user_id=current_user.id)

    # Store assistant message
    assistant_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=response["content"],
        sources=response.get("sources", []),
        tool_calls=response.get("tool_calls", []),
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(
        session_id=session_id,
        message_id=assistant_msg.id,
        content=response["content"],
        sources=response.get("sources", []),
        tool_calls_made=response.get("tool_calls", []),
    )


@router.get("/sessions")
async def list_sessions(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ChatMessage)
        .join(ChatSession)
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()


@router.post("/generate-report")
async def generate_report(
    payload: GenerateReportRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    from app.services.report_service import ReportService
    service = ReportService(db)
    return await service.generate(payload, current_user.id)

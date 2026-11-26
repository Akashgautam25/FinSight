"""
FinSight AI — Notifications Router (price alerts, training jobs)
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update

from app.dependencies import CurrentUser, DBSession
from app.models import Notification

router = APIRouter()


@router.get("")
async def list_notifications(current_user: CurrentUser, db: DBSession, unread_only: bool = Query(False), limit: int = Query(30, le=100)):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    items = (await db.execute(query.order_by(Notification.created_at.desc()).limit(limit))).scalars().all()
    unread = (await db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    )).scalar() or 0
    return {
        "unread_count": unread,
        "items": [{"id": n.id, "type": n.type, "title": n.title, "message": n.message, "payload": n.payload,
                   "is_read": n.is_read, "created_at": n.created_at} for n in items],
    }


@router.post("/read-all")
async def mark_all_read(current_user: CurrentUser, db: DBSession):
    await db.execute(update(Notification).where(Notification.user_id == current_user.id).values(is_read=True))
    await db.commit()
    return {"message": "All notifications marked as read"}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, current_user: CurrentUser, db: DBSession):
    n = (await db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    await db.commit()
    return {"message": "ok"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(notification_id: str, current_user: CurrentUser, db: DBSession):
    n = (await db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(n)
    await db.commit()

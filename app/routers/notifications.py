from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Notification, User
from app.schemas import NotificationOut, NotificationsOut, OkOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsOut)
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    unread = await db.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    items = (await db.scalars(
        select(Notification).where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    )).all()
    return NotificationsOut(
        unread=unread or 0, items=[NotificationOut.model_validate(n) for n in items]
    )


@router.post("/read-all", response_model=OkOut)
async def read_all(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        await db.execute(
            update(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
            .values(read_at=func.now())
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return OkOut()


@router.post("/{notification_id}/read", response_model=OkOut)
async def read_one(
    notification_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        res = await db.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user.id)
            .values(read_at=func.now())
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    if not res.rowcount:
        raise HTTPException(404, "Notifikasi tidak ditemukan")
    return OkOut()

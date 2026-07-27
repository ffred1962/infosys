"""
JSON API для управления уведомлениями в админке (используется JS на странице /admin/notifications).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from core.auth import resolve_admin_access
from db.database import get_session
from models.notification import Notification


logger = logging.getLogger("infosys.api.admin_notification")

router = APIRouter(prefix="/api/admin/notification", tags=["Admin - Уведомления"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class NotificationStateOut(BaseModel):
    id: int
    viewed: bool


@router.patch("/{notification_id}/toggle-viewed", response_model=NotificationStateOut)
def toggle_notification_viewed(
    notification_id: int, request: Request, session: Session = Depends(get_session)
) -> NotificationStateOut:
    _require_admin(request, session)

    target = session.get(Notification, notification_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено.")

    target.viewed = not target.viewed
    session.add(target)
    session.commit()
    session.refresh(target)
    return NotificationStateOut(id=target.id, viewed=target.viewed)


@router.delete("/{notification_id}", status_code=204)
def delete_notification(
    notification_id: int, request: Request, session: Session = Depends(get_session)
) -> None:
    _require_admin(request, session)

    target = session.get(Notification, notification_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено.")

    session.delete(target)
    session.commit()

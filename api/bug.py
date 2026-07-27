"""
JSON API для баг-репортов (кнопка "жучок" в шапке — используется js/bugreport.js).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.bug import Bug
from models.notification import Notification
from models.role import Role
from models.user_role import UserRole


logger = logging.getLogger("infosys.api.bug")

router = APIRouter(prefix="/api/bug", tags=["Bug reports"])


class BugReportIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=2000)

    @field_validator("title")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Описание не может быть пустым.")
        return stripped


class BugReportOut(BaseModel):
    id: int
    title: str


@router.post("", response_model=BugReportOut, status_code=201)
def report_bug(
    payload: BugReportIn, request: Request, session: Session = Depends(get_session)
) -> BugReportOut:
    state, current_user = resolve_authenticated_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Нужно войти, чтобы отправить баг-репорт.")

    bug = Bug(title=payload.title, reporter_id=current_user.id)
    session.add(bug)
    session.flush()  # получаем bug.id, не завершая транзакцию — весь репорт коммитится одним махом

    admin_ids = session.exec(
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "admin")
    ).all()

    msg = f"Новый баг-репорт #{bug.id} от {current_user.email}: {payload.title}"
    for admin_id in admin_ids:
        session.add(Notification(creator_id=current_user.id, receiver_id=admin_id, msg=msg))

    session.commit()
    session.refresh(bug)

    return BugReportOut(id=bug.id, title=bug.title)

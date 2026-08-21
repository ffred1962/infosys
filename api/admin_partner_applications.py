"""
JSON API для рассмотрения анкеты партнёра (используется JS на странице
/admin/partner_applications). Тот же admin-gated AJAX-паттерн, что и
api/admin_bug.py — единственное действие здесь: сохранить статус рассмотрения
и внутренние заметки проверки одной формой. Никакого создания/удаления анкет
через этот API нет — анкеты создаются только публичной формой /anketa/submit.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.auth import resolve_admin_access
from db.database import get_session
from models.application_state import ApplicationState
from models.partner_application import PartnerApplication
from models.users import User


logger = logging.getLogger("infosys.api.admin_partner_applications")

router = APIRouter(prefix="/api/admin/partner_applications", tags=["Admin - Анкеты партнёров"])

# Заметки проверки — внутреннее поле, но всё равно admin-only ввод без явной
# верхней границы был бы небрежностью (тот же принцип, что и _LENGTH_LIMITS в
# routers/anketa.py, просто здесь не единственная защита — вызывающий уже
# аутентифицирован и admin-gated).
MAX_VERIFICATION_NOTES_LENGTH = 5000


def _require_admin(request: Request, session: Session) -> User:
    state, current_user = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")
    return current_user


class ReviewIn(BaseModel):
    status_id: int
    verification_notes: Optional[str] = Field(default=None, max_length=MAX_VERIFICATION_NOTES_LENGTH)


class ReviewOut(BaseModel):
    id: int
    status_id: int
    state_name: str
    verification_notes: Optional[str]
    verified_by: Optional[int]
    verifier_email: Optional[str]
    last_changed: datetime


@router.patch("/{application_id}/review", response_model=ReviewOut)
def review_application(
    application_id: int,
    payload: ReviewIn,
    request: Request,
    session: Session = Depends(get_session),
) -> ReviewOut:
    current_user = _require_admin(request, session)

    application = session.get(PartnerApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Анкета не найдена.")

    state = session.get(ApplicationState, payload.status_id)
    if state is None:
        raise HTTPException(status_code=422, detail="Неизвестный статус рассмотрения.")

    notes = payload.verification_notes.strip() if payload.verification_notes else None

    application.status_id = state.id
    application.verification_notes = notes or None
    # verified_by/last_changed — только сервером, никогда с клиента: любое
    # сохранение этой формы и есть факт "кто-то проверил анкету сейчас".
    application.verified_by = current_user.id
    application.last_changed = datetime.utcnow()
    session.add(application)
    session.commit()
    session.refresh(application)

    return ReviewOut(
        id=application.id,
        status_id=application.status_id,
        state_name=state.name,
        verification_notes=application.verification_notes,
        verified_by=application.verified_by,
        verifier_email=current_user.email,
        last_changed=application.last_changed,
    )

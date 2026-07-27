"""
JSON API для управления системными константами (используется JS на странице /admin/constants).
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.constants import Constant


logger = logging.getLogger("infosys.api.constants")

router = APIRouter(prefix="/api/admin/constants", tags=["Admin - Константы"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class ConstantIn(BaseModel):
    name: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class ConstantOut(BaseModel):
    id: int
    name: str
    value: str
    updated: datetime


def _to_constant_out(constant: Constant) -> ConstantOut:
    return ConstantOut(
        id=constant.id,
        name=constant.name,
        value=constant.value,
        updated=constant.updated,
    )


@router.post("", response_model=ConstantOut, status_code=201)
def create_constant(
    payload: ConstantIn, request: Request, session: Session = Depends(get_session)
) -> ConstantOut:
    _require_admin(request, session)

    name = payload.name.strip()
    value = payload.value.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")
    if not value:
        raise HTTPException(status_code=422, detail="Значение не может быть пустым.")

    existing = session.exec(select(Constant).where(Constant.name == name)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Константа «{name}» уже существует.")

    constant = Constant(name=name, value=value, updated=datetime.utcnow())
    session.add(constant)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Константа «{name}» уже существует.")
    session.refresh(constant)
    return _to_constant_out(constant)


@router.patch("/{constant_id}", response_model=ConstantOut)
def update_constant(
    constant_id: int,
    payload: ConstantIn,
    request: Request,
    session: Session = Depends(get_session),
) -> ConstantOut:
    _require_admin(request, session)

    target = session.get(Constant, constant_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Константа не найдена.")

    name = payload.name.strip()
    value = payload.value.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")
    if not value:
        raise HTTPException(status_code=422, detail="Значение не может быть пустым.")

    existing = session.exec(
        select(Constant).where(Constant.name == name, Constant.id != constant_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Константа «{name}» уже существует.")

    target.name = name
    target.value = value
    target.updated = datetime.utcnow()
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Константа «{name}» уже существует.")
    session.refresh(target)
    return _to_constant_out(target)

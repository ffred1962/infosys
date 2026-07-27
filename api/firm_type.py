"""
JSON API для управления типами фирм (используется JS на странице /admin/firmtype).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.firm_type import FirmType


logger = logging.getLogger("infosys.api.firm_type")

router = APIRouter(prefix="/api/admin/firmtype", tags=["Admin - Типы фирм"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class FirmTypeIn(BaseModel):
    name: str = Field(..., min_length=1)


class FirmTypeOut(BaseModel):
    id: int
    name: str


@router.post("", response_model=FirmTypeOut, status_code=201)
def create_firm_type(
    payload: FirmTypeIn, request: Request, session: Session = Depends(get_session)
) -> FirmTypeOut:
    _require_admin(request, session)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(select(FirmType).where(FirmType.name == name)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Тип фирмы «{name}» уже существует.")

    firm_type = FirmType(name=name)
    session.add(firm_type)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Тип фирмы «{name}» уже существует.")
    session.refresh(firm_type)
    return FirmTypeOut(id=firm_type.id, name=firm_type.name)


@router.patch("/{firm_type_id}", response_model=FirmTypeOut)
def rename_firm_type(
    firm_type_id: int,
    payload: FirmTypeIn,
    request: Request,
    session: Session = Depends(get_session),
) -> FirmTypeOut:
    _require_admin(request, session)

    target = session.get(FirmType, firm_type_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Тип фирмы не найден.")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(
        select(FirmType).where(FirmType.name == name, FirmType.id != firm_type_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Тип фирмы «{name}» уже существует.")

    target.name = name
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Тип фирмы «{name}» уже существует.")
    session.refresh(target)
    return FirmTypeOut(id=target.id, name=target.name)


@router.delete("/{firm_type_id}", status_code=204)
def delete_firm_type(
    firm_type_id: int, request: Request, session: Session = Depends(get_session)
) -> None:
    _require_admin(request, session)

    target = session.get(FirmType, firm_type_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Тип фирмы не найден.")

    session.delete(target)
    session.commit()

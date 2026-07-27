"""
JSON API для управления единицами измерения (используется JS на странице /admin/unit).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.unit import Unit


logger = logging.getLogger("infosys.api.unit")

router = APIRouter(prefix="/api/admin/unit", tags=["Admin - Единицы измерения"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class UnitIn(BaseModel):
    name: str = Field(..., min_length=1)


class UnitOut(BaseModel):
    id: int
    name: str


@router.post("", response_model=UnitOut, status_code=201)
def create_unit(
    payload: UnitIn, request: Request, session: Session = Depends(get_session)
) -> UnitOut:
    _require_admin(request, session)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(select(Unit).where(Unit.name == name)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Единица «{name}» уже существует.")

    unit = Unit(name=name)
    session.add(unit)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Единица «{name}» уже существует.")
    session.refresh(unit)
    return UnitOut(id=unit.id, name=unit.name)


@router.patch("/{unit_id}", response_model=UnitOut)
def rename_unit(
    unit_id: int,
    payload: UnitIn,
    request: Request,
    session: Session = Depends(get_session),
) -> UnitOut:
    _require_admin(request, session)

    target = session.get(Unit, unit_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Единица не найдена.")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(
        select(Unit).where(Unit.name == name, Unit.id != unit_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Единица «{name}» уже существует.")

    target.name = name
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Единица «{name}» уже существует.")
    session.refresh(target)
    return UnitOut(id=target.id, name=target.name)


@router.delete("/{unit_id}", status_code=204)
def delete_unit(unit_id: int, request: Request, session: Session = Depends(get_session)) -> None:
    _require_admin(request, session)

    target = session.get(Unit, unit_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Единица не найдена.")

    session.delete(target)
    session.commit()

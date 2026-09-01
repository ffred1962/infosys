"""
JSON API для управления городами (используется JS на странице /admin/city).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.city import City
from models.firm import Firm
from models.partner_application import PartnerApplication
from models.zakaz import Zakaz


logger = logging.getLogger("infosys.api.city")

router = APIRouter(prefix="/api/admin/city", tags=["Admin - Города"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class CityIn(BaseModel):
    name: str = Field(..., min_length=1)


class CityOut(BaseModel):
    id: int
    name: str


@router.post("", response_model=CityOut, status_code=201)
def create_city(
    payload: CityIn, request: Request, session: Session = Depends(get_session)
) -> CityOut:
    _require_admin(request, session)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(select(City).where(City.name == name)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Город «{name}» уже существует.")

    city = City(name=name)
    session.add(city)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Город «{name}» уже существует.")
    session.refresh(city)
    return CityOut(id=city.id, name=city.name)


@router.patch("/{city_id}", response_model=CityOut)
def rename_city(
    city_id: int,
    payload: CityIn,
    request: Request,
    session: Session = Depends(get_session),
) -> CityOut:
    _require_admin(request, session)

    target = session.get(City, city_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Город не найден.")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(
        select(City).where(City.name == name, City.id != city_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Город «{name}» уже существует.")

    target.name = name
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Город «{name}» уже существует.")
    session.refresh(target)
    return CityOut(id=target.id, name=target.name)


@router.delete("/{city_id}", status_code=204)
def delete_city(city_id: int, request: Request, session: Session = Depends(get_session)) -> None:
    _require_admin(request, session)

    target = session.get(City, city_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Город не найден.")

    firm_in_use = session.exec(select(Firm).where(Firm.city_id == city_id)).first()
    if firm_in_use is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить город «{target.name}» — он используется в фирмах.",
        )

    application_in_use = session.exec(
        select(PartnerApplication).where(PartnerApplication.city_id == city_id)
    ).first()
    if application_in_use is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить город «{target.name}» — по нему есть анкеты партнёров.",
        )

    zakaz_in_use = session.exec(select(Zakaz).where(Zakaz.city_id == city_id)).first()
    if zakaz_in_use is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить город «{target.name}» — он используется в заказах.",
        )

    session.delete(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить город «{target.name}» — он используется в других записях.",
        )

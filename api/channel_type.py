"""
JSON API для управления типами каналов связи (используется JS на странице
/admin/channeltype). Как и у task_status/city/firm_type/unit, нет проверки
"используется ли где-то" при удалении — пока ничто не ссылается на
channel_type через FK; добавить такую проверку в delete_channel_type в тот
день, когда что-то появится (см. CLAUDE.md).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.channel_type import ChannelType


logger = logging.getLogger("infosys.api.channel_type")

router = APIRouter(prefix="/api/admin/channeltype", tags=["Admin - Типы каналов"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class ChannelTypeIn(BaseModel):
    name: str = Field(..., min_length=1)
    is_active: bool = True
    is_input: bool = True
    is_output: bool = True
    icon_url: str = Field(..., min_length=1)


class ChannelTypeOut(BaseModel):
    id: int
    name: str
    is_active: bool
    is_input: bool
    is_output: bool
    icon_url: str


def _to_out(ct: ChannelType) -> ChannelTypeOut:
    return ChannelTypeOut(
        id=ct.id,
        name=ct.name,
        is_active=ct.is_active,
        is_input=ct.is_input,
        is_output=ct.is_output,
        icon_url=ct.icon_url,
    )


@router.post("", response_model=ChannelTypeOut, status_code=201)
def create_channel_type(
    payload: ChannelTypeIn, request: Request, session: Session = Depends(get_session)
) -> ChannelTypeOut:
    _require_admin(request, session)

    name = payload.name.strip()
    icon_url = payload.icon_url.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")
    if not icon_url:
        raise HTTPException(status_code=422, detail="Путь к иконке не может быть пустым.")

    existing = session.exec(select(ChannelType).where(ChannelType.name == name)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Тип канала «{name}» уже существует.")

    channel_type = ChannelType(
        name=name,
        is_active=payload.is_active,
        is_input=payload.is_input,
        is_output=payload.is_output,
        icon_url=icon_url,
    )
    session.add(channel_type)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Тип канала «{name}» уже существует.")
    session.refresh(channel_type)
    return _to_out(channel_type)


@router.patch("/{channel_type_id}", response_model=ChannelTypeOut)
def update_channel_type(
    channel_type_id: int,
    payload: ChannelTypeIn,
    request: Request,
    session: Session = Depends(get_session),
) -> ChannelTypeOut:
    _require_admin(request, session)

    target = session.get(ChannelType, channel_type_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Тип канала не найден.")

    name = payload.name.strip()
    icon_url = payload.icon_url.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")
    if not icon_url:
        raise HTTPException(status_code=422, detail="Путь к иконке не может быть пустым.")

    existing = session.exec(
        select(ChannelType).where(ChannelType.name == name, ChannelType.id != channel_type_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Тип канала «{name}» уже существует.")

    target.name = name
    target.is_active = payload.is_active
    target.is_input = payload.is_input
    target.is_output = payload.is_output
    target.icon_url = icon_url
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Тип канала «{name}» уже существует.")
    session.refresh(target)
    return _to_out(target)


@router.delete("/{channel_type_id}", status_code=204)
def delete_channel_type(
    channel_type_id: int, request: Request, session: Session = Depends(get_session)
) -> None:
    _require_admin(request, session)

    target = session.get(ChannelType, channel_type_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Тип канала не найден.")

    session.delete(target)
    session.commit()

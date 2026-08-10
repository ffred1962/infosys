from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.channel_type import ChannelType
from views.base import render_page


def channel_type_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    channel_types = session.exec(select(ChannelType).order_by(ChannelType.id)).all()

    return render_page(
        request,
        "admin/channel_type.html",
        "Типы каналов",
        "admin",
        {"channel_types": channel_types},
    )

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.firm_type import FirmType
from views.base import render_page


def firm_type_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    firm_types = session.exec(select(FirmType).order_by(FirmType.id)).all()

    return render_page(
        request,
        "admin/firm_type.html",
        "Типы фирм",
        "admin",
        {"firm_types": firm_types},
    )

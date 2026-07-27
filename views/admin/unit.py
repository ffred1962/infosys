from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.unit import Unit
from views.base import render_page


def unit_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    units = session.exec(select(Unit).order_by(Unit.id)).all()

    return render_page(
        request,
        "admin/unit.html",
        "Единицы измерения",
        "admin",
        {"units": units},
    )

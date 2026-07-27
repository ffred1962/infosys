from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.bug import Bug
from models.users import User
from views.base import render_page


def bugs_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    rows = session.exec(
        select(Bug, User.email)
        .join(User, User.id == Bug.reporter_id)
        .order_by(Bug.id.desc())
    ).all()
    bugs = [{"bug": bug, "reporter_email": email} for bug, email in rows]

    return render_page(
        request,
        "admin/bugs.html",
        "Баг-репорты",
        "admin",
        {"bugs": bugs},
    )

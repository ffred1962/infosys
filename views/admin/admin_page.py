from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from core.auth import resolve_admin_access
from db.database import get_session
from views.base import render_page


def admin_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    return render_page(
        request,
        "admin/admin.html",
        "Admin",
        "admin",
        {"current_user_email": current_user.email},
    )

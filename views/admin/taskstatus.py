from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.task_status import TaskStatus
from views.base import render_page


def taskstatus_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    statuses = session.exec(select(TaskStatus).order_by(TaskStatus.id)).all()

    return render_page(
        request,
        "admin/taskstatus.html",
        "Статусы задач",
        "admin",
        {"statuses": statuses},
    )

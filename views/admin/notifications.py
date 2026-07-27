from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.notification import Notification
from models.users import User
from views.base import render_page


def notifications_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    Creator = aliased(User)
    Receiver = aliased(User)
    rows = session.exec(
        select(Notification, Creator.email, Receiver.email)
        .join(Creator, Creator.id == Notification.creator_id)
        .join(Receiver, Receiver.id == Notification.receiver_id)
        .order_by(Notification.id.desc())
    ).all()
    notifications = [
        {"notification": n, "creator_email": creator_email, "receiver_email": receiver_email}
        for n, creator_email, receiver_email in rows
    ]

    return render_page(
        request,
        "admin/notifications.html",
        "Уведомления",
        "admin",
        {"notifications": notifications},
    )

from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.login_info import LoginInfo
from models.users import User
from views.base import render_page


PAGE_SIZE = 30


def _parse_positive_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 1 else None


def login_info_page(
    request: Request,
    page: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    page = _parse_positive_int(page) or 1

    total = session.exec(select(func.count()).select_from(LoginInfo)).one()
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(max(page, 1), total_pages)

    # LEFT JOIN, а не join — у попыток с несуществующим email user_id хранится NULL
    # (см. core.auth.record_login_attempt), inner join такие строки бы просто скрыл.
    rows = session.exec(
        select(LoginInfo, User.email)
        .join(User, User.id == LoginInfo.user_id, isouter=True)
        .order_by(LoginInfo.created.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    attempts = [{"attempt": attempt, "user_email": email} for attempt, email in rows]

    return render_page(
        request,
        "admin/login_info.html",
        "Журнал входов",
        "admin",
        {
            "attempts": attempts,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )

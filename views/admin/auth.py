import re

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, func, select

from core.auth import hash_password, record_login_attempt, verify_password
from db.database import get_session
from models.role import Role
from models.user_role import UserRole
from models.users import User
from views.base import render_page


MIN_PASSWORD_LENGTH = 8

# Один "/" не в начале двойного слэша и не за ним сразу бэкслэш — иначе браузеры
# нормализуют "/\evil.com" в протокол-относительный "//evil.com" (open redirect).
_SAFE_NEXT_RE = re.compile(r"^/(?!/|\\)")


def _safe_redirect_target(next_path: str) -> str:
    return next_path if _SAFE_NEXT_RE.match(next_path) else "/admin"


def setup_first_user(
    request: Request,
    email: str = Form(...),
    fullname: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user_count = session.exec(select(func.count()).select_from(User)).one()
    if user_count > 0:
        # Первый пользователь уже создан кем-то ещё — форма setup больше не актуальна.
        return RedirectResponse(url="/admin", status_code=303)

    if len(password) < MIN_PASSWORD_LENGTH:
        return render_page(
            request,
            "admin/setup.html",
            "Создание администратора",
            "admin",
            {
                "error": f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов.",
                "email": email,
                "fullname": fullname,
                "name": name,
            },
            status_code=400,
        )

    if not fullname.strip():
        return render_page(
            request,
            "admin/setup.html",
            "Создание администратора",
            "admin",
            {
                "error": "Полное имя не может быть пустым.",
                "email": email,
                "fullname": fullname,
                "name": name,
            },
            status_code=400,
        )

    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if admin_role is None:
        return render_page(
            request,
            "admin/setup.html",
            "Создание администратора",
            "admin",
            {"error": "Роль 'admin' не найдена в базе — проверьте миграции.", "email": email, "fullname": fullname, "name": name},
            status_code=500,
        )

    user = User(email=email, fullname=fullname.strip(), name=name, passwordhash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(UserRole(user_id=user.id, role_id=admin_role.id))
    session.commit()

    request.session["user_id"] = user.id
    return RedirectResponse(url="/admin", status_code=303)


def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin"),
    session: Session = Depends(get_session),
):
    redirect_to = _safe_redirect_target(next)
    active_page = "crm" if redirect_to.startswith("/crm") else "admin"
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    user = session.exec(select(User).where(User.email == email)).first()

    # Причина отказа (для login_info) внутренняя — пользователю всегда показывается
    # один и тот же общий текст ниже, чтобы не раскрывать, существует ли аккаунт.
    if user is None:
        record_login_attempt(session, None, client_ip, user_agent, f"пользователь не найден: {email}")
    elif not user.isactive:
        record_login_attempt(session, user.id, client_ip, user_agent, "пользователь отключён")
    elif not verify_password(password, user.passwordhash):
        record_login_attempt(session, user.id, client_ip, user_agent, "неверный пароль")
    else:
        record_login_attempt(session, user.id, client_ip, user_agent, "успех")
        request.session["user_id"] = user.id
        return RedirectResponse(url=redirect_to, status_code=303)

    return render_page(
        request,
        "admin/login.html",
        "Вход",
        active_page,
        {"error": "Неверный email или пароль.", "email": email, "next": redirect_to},
        status_code=400,
    )

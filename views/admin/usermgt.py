import hmac
import secrets
from urllib.parse import urlencode

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import hash_password, resolve_admin_access
from db.database import get_session
from models.role import Role
from models.user_role import UserRole
from models.users import User
from views.admin.auth import MIN_PASSWORD_LENGTH
from views.base import render_page


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


def _get_or_create_csrf_token(request: Request) -> str:
    """Токен привязан к сессионной cookie (не к конкретному пользователю/форме) и
    живёт, пока жива сессия. Нужен только для двух новых, самых чувствительных
    действий этой страницы (edit_user/change_password, см. _verify_csrf) — смена
    пароля произвольного пользователя теперь возможна впервые, а без CSRF-токена
    защитой была бы только SameSite=Lax сессионной cookie."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def _verify_csrf(request: Request, submitted: str) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not hmac.compare_digest(expected, submitted or ""):
        raise HTTPException(
            status_code=403, detail="Недействительный CSRF-токен — обновите страницу и попробуйте снова."
        )


def _redirect_to_user(
    user_id: int,
    error: str | None = None,
    fields: dict[str, str] | None = None,
) -> RedirectResponse:
    """Редирект назад на список с открытой карточкой этого пользователя (см.
    js/usermgt.js: open_user_id/user_error читаются на загрузке страницы и сразу
    открывают нужную модалку) — тот же приём, что и open_firm_id для /crm/firms.
    fields — исходно введённые (но не прошедшие валидацию) значения полей
    редактирования; без них форма при ошибке молча откатывалась бы к тому, что
    реально хранится в БД, и админу пришлось бы вводить их заново."""
    params = {"open_user_id": user_id}
    if error:
        params["user_error"] = error
    if fields:
        params.update(fields)
    return RedirectResponse(url=f"/admin/usermgt?{urlencode(params)}", status_code=303)


def usermgt_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    users = session.exec(select(User).order_by(User.id)).all()
    all_roles = session.exec(select(Role).order_by(Role.name)).all()

    user_roles: dict[int, list[Role]] = {}
    available_roles: dict[int, list[Role]] = {}
    for u in users:
        assigned = session.exec(
            select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)
        ).all()
        user_roles[u.id] = assigned
        assigned_ids = {r.id for r in assigned}
        available_roles[u.id] = [r for r in all_roles if r.id not in assigned_ids]

    return render_page(
        request,
        "admin/usermgt.html",
        "Управление пользователями",
        "admin",
        {
            "users": users,
            "user_roles": user_roles,
            "available_roles": available_roles,
            "current_user_email": current_user.email,
            "csrf_token": _get_or_create_csrf_token(request),
            "open_user_id": request.query_params.get("open_user_id"),
            "user_error": request.query_params.get("user_error"),
            "open_user_email": request.query_params.get("edit_email"),
            "open_user_fullname": request.query_params.get("edit_fullname"),
            "open_user_name": request.query_params.get("edit_name"),
        },
    )


def new_user_form(request: Request, session: Session = Depends(get_session)):
    state, _ = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    return render_page(request, "admin/usermgt_new.html", "Новый пользователь", "admin")


# Form("") ниже (а не Form(...)) на всех строковых form-полях, у которых дальше по
# коду есть собственная проверка на пустоту: Starlette отбрасывает form-поле
# целиком, если его значение — пустая строка (application/x-www-form-urlencoded),
# так что Form(...) увидел бы поле как отсутствующее и упал бы 422 ДО того, как
# выполнится эта проверка. Реальная причина 422 на /new-role при пустом поле —
# именно это, тот же паттерн исправлен во всех похожих полях этого файла.
def create_user(
    request: Request,
    email: str = Form(""),
    fullname: str = Form(""),
    name: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
):
    _require_admin(request, session)

    if len(password) < MIN_PASSWORD_LENGTH:
        return render_page(
            request,
            "admin/usermgt_new.html",
            "Новый пользователь",
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
            "admin/usermgt_new.html",
            "Новый пользователь",
            "admin",
            {
                "error": "Полное имя не может быть пустым.",
                "email": email,
                "fullname": fullname,
                "name": name,
            },
            status_code=400,
        )

    if not email.strip():
        return render_page(
            request,
            "admin/usermgt_new.html",
            "Новый пользователь",
            "admin",
            {"error": "Email не может быть пустым.", "fullname": fullname, "name": name},
            status_code=400,
        )

    if not name.strip():
        return render_page(
            request,
            "admin/usermgt_new.html",
            "Новый пользователь",
            "admin",
            {"error": "Имя не может быть пустым.", "email": email, "fullname": fullname},
            status_code=400,
        )

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing is not None:
        return render_page(
            request,
            "admin/usermgt_new.html",
            "Новый пользователь",
            "admin",
            {
                "error": "Пользователь с таким email уже существует.",
                "fullname": fullname,
                "name": name,
            },
            status_code=400,
        )

    user = User(email=email, fullname=fullname.strip(), name=name, passwordhash=hash_password(password))
    session.add(user)
    session.commit()

    return RedirectResponse(url="/admin/usermgt", status_code=303)


def toggle_active(request: Request, user_id: int, session: Session = Depends(get_session)):
    _require_admin(request, session)

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    target.isactive = not target.isactive
    session.add(target)
    session.commit()
    return RedirectResponse(url="/admin/usermgt", status_code=303)


def assign_role(
    request: Request,
    user_id: int,
    role_id: int = Form(...),
    session: Session = Depends(get_session),
):
    _require_admin(request, session)

    target = session.get(User, user_id)
    role = session.get(Role, role_id)
    if target is None or role is None:
        raise HTTPException(status_code=404, detail="Пользователь или роль не найдены")

    existing = session.exec(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    ).first()
    if existing is None:
        session.add(UserRole(user_id=user_id, role_id=role_id))
        session.commit()

    return _redirect_to_user(user_id)


def remove_role(
    request: Request,
    user_id: int,
    role_id: int = Form(...),
    session: Session = Depends(get_session),
):
    _require_admin(request, session)

    link = session.exec(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    ).first()
    if link is not None:
        session.delete(link)
        session.commit()

    return _redirect_to_user(user_id)


def create_role(
    request: Request,
    user_id: int,
    role_name: str = Form(""),  # см. комментарий над create_user — иначе пустое поле падает 422
    session: Session = Depends(get_session),
):
    _require_admin(request, session)

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    role_name = role_name.strip()
    if role_name:
        role = session.exec(select(Role).where(Role.name == role_name)).first()
        if role is None:
            role = Role(name=role_name)
            session.add(role)
            session.commit()
            session.refresh(role)

        existing = session.exec(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        ).first()
        if existing is None:
            session.add(UserRole(user_id=user_id, role_id=role.id))
            session.commit()

    return _redirect_to_user(user_id)


def edit_user(
    request: Request,
    user_id: int,
    email: str = Form(""),
    fullname: str = Form(""),
    name: str = Form(""),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    _require_admin(request, session)
    _verify_csrf(request, csrf_token)

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    email = email.strip()
    fullname = fullname.strip()
    name = name.strip()
    # Введённые значения — на случай ошибки валидации ниже: без них форма при
    # ошибке молча откатывалась бы к тому, что реально хранится в БД, и админу
    # пришлось бы вводить всё заново (см. _redirect_to_user).
    submitted = {"edit_email": email, "edit_fullname": fullname, "edit_name": name}

    if not email:
        return _redirect_to_user(user_id, "Email не может быть пустым.", submitted)
    if not fullname:
        return _redirect_to_user(user_id, "Полное имя не может быть пустым.", submitted)
    if not name:
        return _redirect_to_user(user_id, "Имя не может быть пустым.", submitted)

    existing = session.exec(select(User).where(User.email == email, User.id != user_id)).first()
    if existing is not None:
        return _redirect_to_user(user_id, "Пользователь с таким email уже существует.", submitted)

    target.email = email
    target.fullname = fullname
    target.name = name
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _redirect_to_user(user_id, "Пользователь с таким email уже существует.", submitted)

    # Успешное сохранение закрывает карточку (обычный редирект, без open_user_id) —
    # переоткрываем её только при ошибке валидации выше, чтобы админ видел, что
    # пошло не так, а не терял место в списке.
    return RedirectResponse(url="/admin/usermgt", status_code=303)


def change_password(
    request: Request,
    user_id: int,
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    _require_admin(request, session)
    _verify_csrf(request, csrf_token)

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if len(new_password) < MIN_PASSWORD_LENGTH:
        return _redirect_to_user(user_id, f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов.")
    if new_password != confirm_password:
        return _redirect_to_user(user_id, "Пароли не совпадают.")

    target.passwordhash = hash_password(new_password)
    session.add(target)
    session.commit()

    return _redirect_to_user(user_id)

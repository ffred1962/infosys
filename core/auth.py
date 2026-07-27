"""
Аутентификация: хеширование паролей и проверка прав пользователя.
"""

import os
from typing import Optional, Tuple

import bcrypt
from fastapi import Request
from sqlmodel import Session, func, select

from models.login_info import LoginInfo
from models.role import Role
from models.user_role import UserRole
from models.users import User


SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-insecure-secret-key-change-me")

# Опционально — помечать ли сессионную cookie флагом Secure (https_only в
# SessionMiddleware). По умолчанию False, т.к. локальная разработка идёт по
# обычному http://127.0.0.1:8000 без TLS — Secure-cookie браузер по такому
# соединению не примет/не отправит, и вход сломается. Включайте
# SESSION_COOKIE_SECURE=true в .env только когда сервис реально доступен по
# HTTPS (ngrok-туннель, прод-деплой) — см. MCP_PUBLIC_BASE_URL в .env.example.
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes")


def hash_password(password: str) -> str:
    """Хеширует пароль через bcrypt (хеш необратим)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль против bcrypt-хеша."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


MAX_LOGIN_INFO_FIELD_LENGTH = 500


def record_login_attempt(
    session: Session, user_id: Optional[int], client_ip: str, user_agent: str, status: str
) -> None:
    """Пишет строку в login_info — по одной на каждую попытку входа (успешную и нет),
    единственная точка входа для этого — login() в views/admin/auth.py, общий для
    /admin и /crm. user_id — None, если введённый email вообще не найден в базе
    (для такой попытки не к кому привязать FK). client_ip/user_agent (из запроса)
    и status (может содержать введённый email, см. вызывающий код) обрезаются —
    всё поступает от анонимного клиента ДО какой-либо проверки, так что без лимита
    длины это был бы дешёвый способ раздувать таблицу очень длинными строками."""
    session.add(
        LoginInfo(
            user_id=user_id,
            client_ip=client_ip[:MAX_LOGIN_INFO_FIELD_LENGTH],
            user_agent=user_agent[:MAX_LOGIN_INFO_FIELD_LENGTH],
            status=status[:MAX_LOGIN_INFO_FIELD_LENGTH],
        )
    )
    session.commit()


def get_current_user(request: Request, session: Session) -> Optional[User]:
    """Возвращает текущего пользователя из сессии, либо None, если вход не выполнен."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return session.get(User, user_id)


def user_has_role(session: Session, user_id: int, role_name: str) -> bool:
    """Проверяет, назначена ли пользователю указанная роль."""
    statement = (
        select(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.name == role_name)
    )
    return session.exec(statement).first() is not None


def resolve_authenticated_access(request: Request, session: Session) -> Tuple[str, Optional[User]]:
    """Определяет состояние доступа к разделам, куда пускается любой активный пользователь (без проверки роли).

    Возвращает кортеж (state, user):
      - ("login", None) — пользователь не аутентифицирован (или отключён — isactive=False
                           считается разлогиненным, как и в resolve_admin_access)
      - ("ok", user)     — аутентифицированный активный пользователь
    """
    current_user = get_current_user(request, session)
    if current_user is None or not current_user.isactive:
        return "login", None

    return "ok", current_user


def resolve_admin_access(request: Request, session: Session) -> Tuple[str, Optional[User]]:
    """Определяет состояние доступа к разделу /admin.

    Возвращает кортеж (state, user):
      - ("setup", None)     — таблица user пуста, нужно создать первого администратора
      - ("login", None)     — пользователь не аутентифицирован (или отключён — isactive=False
                               считается разлогиненным, чтобы деактивация выкидывала уже вошедших)
      - ("forbidden", None) — аутентифицирован, но не обладает ролью admin
      - ("ok", user)        — аутентифицированный активный администратор
    """
    user_count = session.exec(select(func.count()).select_from(User)).one()
    if user_count == 0:
        return "setup", None

    current_user = get_current_user(request, session)
    if current_user is None or not current_user.isactive:
        return "login", None

    if not user_has_role(session, current_user.id, "admin"):
        return "forbidden", None

    return "ok", current_user

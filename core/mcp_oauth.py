"""
Собственный OAuth 2.1 authorization server для MCP-моста (смонтирован в корне
приложения — см. api/mcp_server.py за тем, почему не под префиксом /infosys_mcp).

Почему не статический API-ключ (как в первой версии этого моста): удалённые
MCP-коннекторы Claude (claude.ai/Claude Desktop, подключаемые не с той же
машины, где крутится сервер) не поддерживают произвольный заголовок с
секретом — они либо работают с полностью открытым сервером, либо проходят
настоящий OAuth 2.1 Authorization Code + PKCE флоу, обнаруживая эндпоинты через
/.well-known/oauth-authorization-server. Так что здесь реализован именно он.

Ключевое отличие от первой версии: авторизация происходит от лица РЕАЛЬНОГО
пользователя InfoSys, а не одного захардкоженного сервис-аккаунта.
/authorize (см. api/mcp_server.py:oauth_login) переиспользует уже
существующий механизм логина (core.auth.resolve_authenticated_access, тот же
/admin/login с next-редиректом) — то есть каждый, кто подключает Claude,
логинится под своим обычным InfoSys-аккаунтом, и все MCP-инструменты дальше
работают с его реальными правами (в т.ч. проверки роли admin). Это даёт
доступ с любого компьютера, а не только с машины, где запущен сервер.

Хранилище (клиенты/коды/токены) — только в памяти процесса, не в
data/infosys.db: это демо-масштаб реализации (истекающие короткоживущие коды и
токены, не обязательно переживающие рестарт процесса ради корректности), а не
полноценный production OAuth-сервер, готовый работать за несколькими
воркерами/за балансировщиком. Если это станет проблемой — вынести в БД.
"""

import secrets
import time
from dataclasses import dataclass
from typing import Optional

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlmodel import Session, select

from models.users import User

ACCESS_TOKEN_TTL_SECONDS = 60 * 60  # 1 час
REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 дней
AUTHORIZATION_CODE_TTL_SECONDS = 5 * 60  # 5 минут — как рекомендует RFC 6749 §10.5


@dataclass
class _PendingAuthorization:
    """Параметры /authorize, отложенные до тех пор, пока пользователь не
    залогинится в InfoSys и не подтвердит доступ на /oauth_login."""

    client: OAuthClientInformationFull
    params: AuthorizationParams
    expires_at: float
    # Привязывается к email того, кто первым открыл страницу согласия для этого
    # request_id (см. api/mcp_server.py:oauth_login) — не даёт злоумышленнику
    # прислать жертве, у которой уже открыта сессия InfoSys, ссылку на СВОЙ
    # запрос авторизации и получить решение "Разрешить" от её имени вместо своего
    # (классический OAuth login/consent CSRF): при несовпадении email на
    # повторном заходе запрос отклоняется, а не молча одобряется.
    locked_to_email: Optional[str] = None


class InfosysOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    def __init__(self) -> None:
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._pending: dict[str, _PendingAuthorization] = {}
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._access_tokens: dict[str, AccessToken] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}
        # Перекрёстные ссылки access<->refresh — access_token/refresh_token сами по
        # себе просто два независимых случайных значения, ничем не связанные, так
        # что revoke_token (вызывается с одним из них) не может иначе понять, какой
        # второй токен из той же выдачи тоже нужно аннулировать.
        self._access_to_refresh: dict[str, str] = {}
        self._refresh_to_access: dict[str, str] = {}

    # --- Регистрация клиентов (RFC 7591 dynamic client registration) ---

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info

    # --- /authorize: откладываем решение до логина+подтверждения на нашей стороне ---

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        request_id = secrets.token_urlsafe(24)
        self._pending[request_id] = _PendingAuthorization(
            client=client, params=params, expires_at=time.time() + AUTHORIZATION_CODE_TTL_SECONDS
        )
        return f"/oauth_login?req={request_id}"

    def get_pending(self, request_id: str) -> Optional[_PendingAuthorization]:
        pending = self._pending.get(request_id)
        if pending is None or pending.expires_at < time.time():
            self._pending.pop(request_id, None)
            return None
        return pending

    def complete_authorization(self, request_id: str, user_email: str) -> str:
        """Вызывается из api/mcp_server.py:oauth_login после логина и согласия —
        генерирует одноразовый код и возвращает URL финального редиректа к клиенту
        (Claude), тот же redirect_uri/state, что были в исходном /authorize."""
        pending = self.get_pending(request_id)
        if pending is None:
            raise ValueError("Запрос авторизации не найден или истёк — начните заново в Claude.")
        del self._pending[request_id]

        code = secrets.token_urlsafe(32)
        self._auth_codes[code] = AuthorizationCode(
            code=code,
            scopes=pending.params.scopes or [],
            expires_at=time.time() + AUTHORIZATION_CODE_TTL_SECONDS,
            client_id=pending.client.client_id,
            code_challenge=pending.params.code_challenge,
            redirect_uri=pending.params.redirect_uri,
            redirect_uri_provided_explicitly=pending.params.redirect_uri_provided_explicitly,
            subject=user_email,
        )
        return construct_redirect_uri(str(pending.params.redirect_uri), code=code, state=pending.params.state)

    def deny_authorization(self, request_id: str) -> str:
        """Пользователь нажал "Отмена" на странице согласия — редирект с
        error=access_denied, как того требует RFC 6749 §4.1.2.1."""
        pending = self.get_pending(request_id)
        if pending is None:
            raise ValueError("Запрос авторизации не найден или истёк — начните заново в Claude.")
        del self._pending[request_id]
        return construct_redirect_uri(
            str(pending.params.redirect_uri), error="access_denied", state=pending.params.state
        )

    # --- /token: обмен authorization_code / refresh_token на access_token ---

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[AuthorizationCode]:
        return self._auth_codes.get(authorization_code)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        # Код одноразовый — использованный сразу забываем, чтобы его нельзя было
        # предъявить повторно (replay), даже если он ещё не истёк по времени.
        self._auth_codes.pop(authorization_code.code, None)
        return self._issue_tokens(client.client_id, authorization_code.scopes, authorization_code.subject)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[RefreshToken]:
        return self._refresh_tokens.get(refresh_token)

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Ротация refresh-токена при каждом обмене — если старый когда-то утечёт и
        # будет предъявлен повторно позже, он уже недействителен. Чистим и
        # перекрёстные ссылки, чтобы не оставались указывающими в никуда.
        old_refresh = refresh_token.token
        self._refresh_tokens.pop(old_refresh, None)
        old_access = self._refresh_to_access.pop(old_refresh, None)
        if old_access is not None:
            self._access_to_refresh.pop(old_access, None)
        return self._issue_tokens(client.client_id, scopes or refresh_token.scopes, refresh_token.subject)

    def _issue_tokens(self, client_id: str, scopes: list[str], subject: Optional[str]) -> OAuthToken:
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        access_expires_at = int(time.time()) + ACCESS_TOKEN_TTL_SECONDS
        refresh_expires_at = int(time.time()) + REFRESH_TOKEN_TTL_SECONDS

        self._access_tokens[access_token] = AccessToken(
            token=access_token, client_id=client_id, scopes=scopes, expires_at=access_expires_at, subject=subject
        )
        self._refresh_tokens[refresh_token] = RefreshToken(
            token=refresh_token, client_id=client_id, scopes=scopes, expires_at=refresh_expires_at, subject=subject
        )
        self._access_to_refresh[access_token] = refresh_token
        self._refresh_to_access[refresh_token] = access_token
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            refresh_token=refresh_token,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        access_token = self._access_tokens.get(token)
        if access_token is None:
            return None
        if access_token.expires_at is not None and access_token.expires_at < time.time():
            self._access_tokens.pop(token, None)
            return None
        return access_token

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        # token может быть либо AccessToken, либо RefreshToken — в обоих случаях
        # аннулируем ОБА токена одной выдачи (см. provider.py docstring: "SHOULD
        # revoke both... regardless of which... is provided"), а не только тот,
        # что предъявили, иначе оставшийся токен продолжает молча действовать.
        access_value = token.token if isinstance(token, AccessToken) else self._refresh_to_access.get(token.token)
        refresh_value = token.token if isinstance(token, RefreshToken) else self._access_to_refresh.get(token.token)

        if access_value is not None:
            self._access_tokens.pop(access_value, None)
            self._access_to_refresh.pop(access_value, None)
        if refresh_value is not None:
            self._refresh_tokens.pop(refresh_value, None)
            self._refresh_to_access.pop(refresh_value, None)


oauth_provider = InfosysOAuthProvider()


def resolve_user_by_subject(session: Session, subject: Optional[str]) -> Optional[User]:
    """AccessToken.subject хранит email пользователя InfoSys, подтвердившего
    доступ на /oauth_login — превращает это обратно в реальную
    запись User (и отсеивает деактивированных — та же логика, что и
    resolve_authenticated_access, на случай если пользователя отключили уже
    после выдачи токена)."""
    if not subject:
        return None
    user = session.exec(select(User).where(User.email == subject)).first()
    if user is None or not user.isactive:
        return None
    return user

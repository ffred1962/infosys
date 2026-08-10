"""
MCP-сервер (Model Context Protocol) — мост между Claude (Desktop/claude.ai) и
InfoSys, смонтированный В КОРНЕ того же FastAPI-приложения (main.py):
app.mount("/", infosys_mcp.streamable_http_app()), а не под каким-либо
префиксом типа /infosys_mcp (так было в первой версии — исправлено после
живого наблюдения: Claude, подключаясь через ngrok, запрашивал
/.well-known/oauth-authorization-server и /register прямо в корне домена, а не
под префиксом). Discovery-эндпоинты OAuth (RFC 8414/RFC 9728) по конвенции
живут в корне origin'а, а не под произвольным путём — если бы это был просто
статический API-ключ без discovery, префикс был бы не важен, но раз тут
настоящий OAuth, префикс ломает обнаружение реальными клиентами. Из-за этого
сам ресурс MCP теперь на {MCP_PUBLIC_BASE_URL}/mcp, а не .../infosys_mcp/mcp —
и это единственный мост-специфичный кусок API этого проекта, у которого нет
общего префикса пути (см. middlewares/no_cache.py, где вместо одного префикса
перечислены все конкретные пути моста). Живёт в api/, а не в core/ (несмотря
на то, что не использует APIRouter/include_router, а монтируется через
app.mount()) — потому что переиспользует бизнес-логику api/plus.py, а core/ по
соглашению проекта ничего не импортирует из api/ (обратная зависимость).

Почему отдельный мост, а не просто "скормить" Claude наши /api/*: Claude умеет
говорить только по протоколу MCP, а не по произвольному REST/OpenAPI (в
отличие, например, от Custom GPT Actions) — нужен отдельный слой, переводящий
вызовы MCP-инструментов в вызовы уже существующей бизнес-логики.

Аутентификация — полноценный OAuth 2.1 (Authorization Code + PKCE), а не
статический API-ключ (первая версия этого моста, core/mcp_auth.py, была именно
такой — теперь не используется и оставлена только как git-история): удалённые
коннекторы Claude (не с той же машины, где крутится сервер) не поддерживают
произвольный заголовок с секретом, а ожидают либо полностью открытый сервер,
либо настоящий OAuth с discovery через /.well-known/oauth-authorization-server
и (опционально) динамической регистрацией клиента (RFC 7591). См.
core/mcp_oauth.py за самим authorization-server провайдером — авторизация там
происходит от лица РЕАЛЬНОГО пользователя InfoSys (переиспользует обычный
/admin/login с next-редиректом), а не одного захардкоженного сервис-аккаунта,
поэтому мост работает с любого компьютера, где у человека уже есть аккаунт
InfoSys, а не только с машины, где запущен сервер.

Каждый tool читает личность вызывающего через
mcp.server.auth.middleware.auth_context.get_access_token() — это работает,
потому что FastMCP оборачивает наш streamable_http_app() в
AuthenticationMiddleware/AuthContextMiddleware, когда сконфигурирован
token_verifier (см. ниже), и достаёт Bearer-токен из заголовка Authorization
запроса сам. access_token.subject хранит email пользователя, подтвердившего
доступ — core.mcp_oauth.resolve_user_by_subject превращает это обратно в
реальную запись User. Каждый tool открывает свою короткоживущую SQLModel
Session напрямую через db.database.engine — MCP tools не FastAPI-роуты,
поэтому Depends(get_session) здесь недоступен.

Бизнес-логику переиспользуем, а не дублируем: search_firms_tool — та же
последовательность действий, что и POST /api/firm/search (api/firm.py:search),
list_my_tasks — тот же запрос, что строит /crm/tasks (views/crm/tasks.py).
Прямой вызов существующих FastAPI-роутов отсюда невозможен без искусственно
сконструированного Request/session (они читают request.session["user_id"]) —
поэтому вместо этого переиспользуются их SQLModel-запросы/хелперы напрямую.

Первая версия — сознательно небольшой набор инструментов (арифметика для
проверки моста, поиск/просмотр фирм, просмотр своих задач), не все admin-гейтед
эндпоинты api/ — см. обсуждение с пользователем перед реализацией.
"""

import logging
import os
from typing import Optional

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import aliased
from sqlmodel import Session, select
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from api.plus import PlusRequest
from api.plus import plus as plus_endpoint
from core.auth import resolve_authenticated_access, user_has_role
from core.firm_search import FirmSearchError, search_firms
from core.mcp_oauth import oauth_provider, resolve_user_by_subject
from db.database import engine
from models.city import City
from models.firm import Firm
from models.firm_type import FirmType
from models.task import Task
from models.task_status import TaskStatus
from models.users import User
from views.base import render_page

logger = logging.getLogger("infosys.mcp")

# Базовый публичный URL, по которому Claude реально достучится до этого сервера —
# локально это http://127.0.0.1:8000, при пробросе через ngrok/облако — тот
# внешний https-адрес. Меняется при каждом перезапуске туннеля (бесплатный
# ngrok выдаёт новый поддомен каждый раз) — тогда нужно обновить .env и
# переподключить коннектор в Claude заново (сохранённый ранее клиент/токены
# всё равно живут только в памяти процесса и пропадают при рестарте сервера).
MCP_PUBLIC_BASE_URL = os.environ.get("MCP_PUBLIC_BASE_URL", "http://127.0.0.1:8000")

mcp = FastMCP(
    "InfoSys",
    instructions=(
        "Инструменты для CRM InfoSys: поиск и просмотр фирм, просмотр своих задач, "
        "сложение чисел для проверки связи. Каждый вызов выполняется от имени того "
        "InfoSys-пользователя, который прошёл OAuth-авторизацию в браузере при "
        "подключении этого коннектора."
    ),
    auth_server_provider=oauth_provider,
    auth=AuthSettings(
        issuer_url=MCP_PUBLIC_BASE_URL,
        resource_server_url=f"{MCP_PUBLIC_BASE_URL}/mcp",
        client_registration_options=ClientRegistrationOptions(
            enabled=True, default_scopes=["infosys"]
        ),
        revocation_options=RevocationOptions(enabled=True),
    ),
    # FastMCP включает DNS-rebinding-защиту, ограниченную localhost, автоматически,
    # когда host="127.0.0.1" (значение по умолчанию, не меняем — сам процесс
    # по-прежнему слушает только локально, наружу торчит через отдельный туннель/
    # прокси типа ngrok или будущий облачный балансировщик). Эта защита проверяет
    # заголовок Host запроса — при работе через ngrok/облако он не будет localhost,
    # поэтому явно отключаем здесь: Host-валидацию в таком случае должен
    # обеспечивать сам туннель/прокси, а не эта библиотека.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _current_session_and_user() -> tuple[Session, User]:
    """Общий вход каждого tool'а: берёт email пользователя из Bearer-токена
    текущего MCP-запроса (get_access_token() — контекстная переменная,
    заполняемая AuthContextMiddleware до вызова tool'а) и открывает сессию БД."""
    access_token = get_access_token()
    session = Session(engine)
    user = resolve_user_by_subject(session, access_token.subject if access_token else None)
    if user is None:
        session.close()
        raise PermissionError(
            "Не удалось определить пользователя InfoSys по токену — переподключите коннектор в Claude."
        )
    return session, user


@mcp.tool()
def whoami() -> dict:
    """Показывает, от имени какого пользователя InfoSys сейчас выполняются вызовы
    этого MCP-сервера (полезно для проверки, что авторизация прошла верно)."""
    session, user = _current_session_and_user()
    try:
        is_admin = user_has_role(session, user.id, "admin")
    finally:
        session.close()
    return {"email": user.email, "fullname": user.fullname, "is_admin": is_admin}


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Складывает два числа — обёртка над POST /api/plus, для проверки связи."""
    session, _ = _current_session_and_user()
    session.close()
    return plus_endpoint(PlusRequest(a=a, b=b)).result


@mcp.tool()
def search_firms_tool(city: str, firm_type: str) -> list[dict]:
    """
    Ищет реальные фирмы заданного типа в заданном городе через веб-поиск и
    сохраняет новые найденные фирмы в общую таблицу firm — то же самое, что кнопка
    ПОИСК на /crm/firm_finder. Возвращает только новые фирмы (уже известные по
    имени в этом городе/типе пропускаются). city и firm_type — точные названия из
    справочников (например "Киев", "магазин дверей") — используйте list_firms_tool
    или list_cities_and_types, если названия не известны заранее.
    """
    session, user = _current_session_and_user()
    try:
        city_row = session.exec(select(City).where(City.name == city)).first()
        if city_row is None:
            raise ValueError(f"Город не найден в справочнике City: {city!r}")
        type_row = session.exec(select(FirmType).where(FirmType.name == firm_type)).first()
        if type_row is None:
            raise ValueError(f"Тип фирмы не найден в справочнике FirmType: {firm_type!r}")

        try:
            found = search_firms(city_row.name, type_row.name)
        except FirmSearchError as exc:
            raise RuntimeError(str(exc)) from exc

        existing_names = {
            name.strip().lower()
            for name in session.exec(
                select(Firm.name).where(Firm.city_id == city_row.id, Firm.type_id == type_row.id)
            ).all()
        }

        created: list[Firm] = []
        for item in found:
            key = item["name"].strip().lower()
            if key in existing_names:
                continue
            existing_names.add(key)
            firm = Firm(
                city_id=city_row.id,
                type_id=type_row.id,
                user_id=user.id,
                name=item["name"],
                phone=item["phone"],
                website=item["website"],
                address=item["address"],
                source=item["source"],
                notes=item["notes"],
            )
            session.add(firm)
            created.append(firm)

        session.commit()
        return [
            {"name": f.name, "phone": f.phone, "website": f.website, "address": f.address}
            for f in created
        ]
    finally:
        session.close()


MAX_LIST_FIRMS_LIMIT = 50


@mcp.tool()
def list_firms_tool(
    city: Optional[str] = None,
    firm_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Список фирм из общей таблицы firm (как /crm/firms), новые сверху, с
    опциональным фильтром по точному названию города и/или типа фирмы.
    limit ограничен 50 — для более полного просмотра используйте фильтры."""
    session, _ = _current_session_and_user()
    try:
        limit = max(1, min(limit, MAX_LIST_FIRMS_LIMIT))
        query = (
            select(Firm, City.name, FirmType.name)
            .join(City, City.id == Firm.city_id)
            .join(FirmType, FirmType.id == Firm.type_id)
        )
        if city:
            query = query.where(City.name == city)
        if firm_type:
            query = query.where(FirmType.name == firm_type)
        rows = session.exec(query.order_by(Firm.id.desc()).limit(limit)).all()
        return [
            {
                "id": f.id,
                "name": f.name,
                "city": city_name,
                "type": type_name,
                "phone": f.phone,
                "website": f.website,
                "address": f.address,
                "rating": f.rating,
            }
            for f, city_name, type_name in rows
        ]
    finally:
        session.close()


@mcp.tool()
def list_cities_and_types() -> dict:
    """Справочные значения для search_firms_tool/list_firms_tool: точные названия
    городов (City) и типов фирм (FirmType), заведённые в системе."""
    session, _ = _current_session_and_user()
    try:
        cities = session.exec(select(City.name).order_by(City.name)).all()
        types = session.exec(select(FirmType.name).order_by(FirmType.name)).all()
        return {"cities": list(cities), "firm_types": list(types)}
    finally:
        session.close()


@mcp.tool()
def list_my_tasks(role: str = "assignee") -> list[dict]:
    """
    Список задач текущего пользователя. role="assignee" (по умолчанию) — задачи,
    назначенные ему; role="author" — задачи, которые он выдал сам.
    """
    if role not in ("assignee", "author"):
        raise ValueError('role должен быть "assignee" или "author"')
    session, user = _current_session_and_user()
    try:
        Other = aliased(User)
        own_col = Task.assignee_id if role == "assignee" else Task.author_id
        other_col = Task.author_id if role == "assignee" else Task.assignee_id
        other_label = "author" if role == "assignee" else "assignee"

        rows = session.exec(
            select(Task, Other.fullname, TaskStatus.name)
            .join(Other, Other.id == other_col)
            .join(TaskStatus, TaskStatus.id == Task.status_id)
            .where(own_col == user.id)
            .order_by(Task.id.desc())
        ).all()
        return [
            {
                "id": t.id,
                "title": t.title,
                "due_date": str(t.due_date),
                "status": status_name,
                "completed": t.completed,
                other_label: other_name,
            }
            for t, other_name, status_name in rows
        ]
    finally:
        session.close()


# --- /oauth_login: авторизация от лица реального пользователя ---
# Не защищено токеном (custom_route по определению SDK предназначен именно для
# шагов OAuth-флоу) — здесь работает обычная сессионная cookie InfoSys, та же,
# что и на /admin, /crm.


@mcp.custom_route("/oauth_login", methods=["GET", "POST"])
async def oauth_login(request: Request) -> Response:
    if request.method == "POST":
        form = await request.form()
        req_id = form.get("req")
        decision = form.get("decision")
    else:
        req_id = request.query_params.get("req")
        decision = None

    if not req_id or not isinstance(req_id, str):
        return PlainTextResponse("Отсутствует параметр req.", status_code=400)

    pending = oauth_provider.get_pending(req_id)
    if pending is None:
        return PlainTextResponse(
            "Запрос авторизации не найден или истёк — начните заново в Claude.", status_code=400
        )

    session = Session(engine)
    try:
        state, current_user = resolve_authenticated_access(request, session)
        if state == "login":
            next_url = f"/oauth_login?req={req_id}"
            return render_page(request, "admin/login.html", "Вход", "admin", {"next": next_url})

        # Привязываем этот конкретный req к тому, кто первым его открыл — иначе
        # атакующий мог бы начать свой собственный OAuth-флоу, а затем прислать
        # жертве (у которой уже открыта сессия InfoSys) ссылку на СВОЙ req_id,
        # получив решение "Разрешить" от её имени вместо своего собственного.
        if pending.locked_to_email is None:
            pending.locked_to_email = current_user.email
        elif pending.locked_to_email != current_user.email:
            return PlainTextResponse(
                "Этот запрос авторизации уже открыт другим пользователем — начните заново в Claude.",
                status_code=403,
            )

        if request.method == "GET":
            return render_page(
                request,
                "mcp_oauth_consent.html",
                "Разрешить доступ",
                "admin",
                {
                    "client_name": pending.client.client_name or pending.client.client_id,
                    "user_email": current_user.email,
                    "req": req_id,
                },
            )

        try:
            if decision == "allow":
                redirect_url = oauth_provider.complete_authorization(req_id, current_user.email)
            else:
                redirect_url = oauth_provider.deny_authorization(req_id)
        except ValueError as exc:
            return PlainTextResponse(str(exc), status_code=400)

        return RedirectResponse(url=redirect_url, status_code=302)
    finally:
        session.close()

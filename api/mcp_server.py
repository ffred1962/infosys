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
from datetime import datetime
from typing import Optional

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import aliased
from sqlmodel import Session, select
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from api.firm import FirmPriceDownloadOut, _persist_price_items, _prepare_price_items
from api.plus import PlusRequest
from api.plus import plus as plus_endpoint
from core.auth import resolve_authenticated_access, user_has_role
from core.firm_search import FirmSearchError, search_firms
from core.mcp_oauth import oauth_provider, resolve_user_by_subject
from db.database import engine
from models.city import City
from models.constants import Constant
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
        "сложение чисел для проверки связи, а также очередь заданий для ИИ "
        "(list_ai_tasks/submit_firm_price_items/complete_ai_task) — задачи, "
        "назначенные на служебного пользователя AI_USER_ID (см. /admin/constants), "
        "предназначены для выполнения этим самым коннектором. Каждый вызов "
        "выполняется от имени того InfoSys-пользователя, который прошёл "
        "OAuth-авторизацию в браузере при подключении этого коннектора."
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


# --- Очередь заданий для внешнего Claude Code (см. обсуждение с пользователем):
# любой человек ставит обычную Task, назначая исполнителем служебного
# "ИИ"-пользователя (его id хранится в constants.AI_USER_ID, настраивается
# через /admin/constants, без изменений кода) — а внешний Claude Code,
# подключённый к этому мосту по MCP (с любого InfoSys-аккаунта, не обязательно
# от имени самого AI_USER_ID), читает эту очередь через list_ai_tasks и решает
# задачи сам, своими штатными средствами (веб-поиск/фетч), не тратя
# оплачиваемые вызовы Anthropic API, которые тратит core/firm_price_download.py.
# Результат скачивания прайса кладётся через submit_firm_price_items, а сама
# задача закрывается через complete_ai_task.


def _get_ai_user_id(session: Session) -> int:
    """Читает id "ИИ"-пользователя из constants.AI_USER_ID. Это единственная
    точка привязки очереди заданий к конкретному User — если константа не
    задана или битая, все инструменты очереди ниже явно скажут, что делать."""
    const = session.exec(select(Constant).where(Constant.name == "AI_USER_ID")).first()
    if const is None:
        raise ValueError(
            "Константа AI_USER_ID не задана — добавьте её в /admin/constants "
            "(значение = id пользователя, на которого назначаются задачи для ИИ)."
        )
    try:
        ai_user_id = int(const.value)
    except ValueError:
        raise ValueError(f"Константа AI_USER_ID содержит не число: {const.value!r}")
    if session.get(User, ai_user_id) is None:
        raise ValueError(f"Пользователь с id={ai_user_id} (из константы AI_USER_ID) не найден.")
    return ai_user_id


@mcp.tool()
def list_ai_tasks() -> list[dict]:
    """
    Список незавершённых задач, назначенных на служебного "ИИ"-пользователя
    (см. константу AI_USER_ID в /admin/constants) — это и есть очередь заданий
    для автоматизации. В отличие от list_my_tasks (которая смотрит на самого
    вызывающего), эта смотрит на AI_USER_ID независимо от того, под каким
    InfoSys-аккаунтом сейчас подключён коннектор. title/description задачи
    описывают, что нужно сделать (например "Скачать прайс: ООО Ромашка") —
    для конкретной фирмы используйте list_firms_tool/list_cities_and_types,
    чтобы найти её id по названию из текста задачи.
    """
    session, _ = _current_session_and_user()
    try:
        ai_user_id = _get_ai_user_id(session)
        rows = session.exec(
            select(Task, User.fullname, TaskStatus.name)
            .join(User, User.id == Task.author_id)
            .join(TaskStatus, TaskStatus.id == Task.status_id)
            .where(Task.assignee_id == ai_user_id, Task.completed.is_(False))
            .order_by(Task.due_date)
        ).all()
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": str(t.due_date),
                "status": status_name,
                "author": author_name,
            }
            for t, author_name, status_name in rows
        ]
    finally:
        session.close()


MAX_SUBMIT_PRICE_ITEMS = 200


@mcp.tool()
def submit_firm_price_items(firm_id: int, items: list[dict], note: Optional[str] = None) -> dict:
    """
    Сохраняет прайс-лист фирмы, уже найденный и разобранный самим вызывающим
    (например Claude Code, скачавшим и прочитавшим сайт фирмы своими штатными
    средствами) — парная операция к кнопке "Скачать прайс" на
    /crm/firms/{id}/prices, но без платного похода в Anthropic API: сам шаг
    извлечения данных уже сделан снаружи, этот инструмент только сохраняет
    результат. items — список товаров (не более MAX_SUBMIT_PRICE_ITEMS штук за
    вызов), каждый в виде {"name": str (обязательно, непустая строка),
    "article": str|null, "unit": str|null, "price": str|число} (article/unit
    можно не указывать — будут доопределены так же, как при обычном скачивании:
    артикул — по началу названия или транслитерацией, единица — по словарю
    синонимов, по умолчанию "шт"; price принимает и строку с валютой/
    разделителями тысяч). Создаёт новую запись firm_price (дата — сегодня) и
    связанные/переиспользованные firm_goods + firm_price_body, та же логика,
    что и у обычного скачивания. Доступно любому авторизованному пользователю,
    без ограничения владельцем фирмы — как и остальные инструменты работы с
    фирмами в этом мосту.
    """
    session, user = _current_session_and_user()
    try:
        firm = session.get(Firm, firm_id)
        if firm is None:
            raise ValueError(f"Фирма с id={firm_id} не найдена.")

        # Явная валидация формы items перед _prepare_price_items() — та функция
        # написана для внутреннего, уже гарантированно правильного формата
        # (ответ core.firm_price_download, см. api/firm.py), и на "item['name']"
        # без проверки наличия ключа падает необработанным KeyError. Здесь же
        # items приходит от внешнего вызывающего (стороннего Claude Code) —
        # ошибка должна быть понятной, а не голым "'name'".
        if not isinstance(items, list) or not items:
            raise ValueError('items должен быть непустым списком объектов вида {"name": ..., "price": ...}.')
        if len(items) > MAX_SUBMIT_PRICE_ITEMS:
            raise ValueError(
                f"Слишком много товаров за один вызов ({len(items)}, максимум {MAX_SUBMIT_PRICE_ITEMS}) "
                "— разбейте на несколько вызовов."
            )
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
                raise ValueError('Каждый элемент items должен быть объектом с непустой строкой "name".')

        prepared = _prepare_price_items(items)
        if not prepared:
            raise ValueError("Не найдено ни одного валидного товара с ценой в переданных items.")

        rem = note or f"Загружено ИИ-агентом (Claude Code) от имени {user.email}"
        result: FirmPriceDownloadOut = _persist_price_items(session, firm, prepared, rem)
        return {"price_id": result.price_id, "created": str(result.created), "item_count": result.item_count}
    finally:
        session.close()


@mcp.tool()
def complete_ai_task(task_id: int, status: Optional[str] = None) -> dict:
    """
    Закрывает задачу, назначенную на служебного "ИИ"-пользователя (AI_USER_ID) —
    ставит completed=True и date_finished=сейчас. Это осознанное исключение из
    обычного правила проекта "закрыть задачу может только автор" (см.
    api/task.py) — распространяется ТОЛЬКО на задачи, где
    assignee_id == AI_USER_ID; на любые другие задачи (в т.ч. свои собственные
    у вызывающего) этот инструмент не действует. status (необязательно) —
    точное название статуса из справочника TaskStatus (например "выполнена"),
    если нужно заодно сменить и его — обычно это делает исполнитель через
    PATCH /api/task/{id}/status, но здесь для простоты можно одним вызовом.
    """
    session, _ = _current_session_and_user()
    try:
        ai_user_id = _get_ai_user_id(session)
        task = session.get(Task, task_id)
        if task is None or task.assignee_id != ai_user_id:
            raise ValueError(f"Задача id={task_id}, назначенная на AI_USER_ID, не найдена.")

        if status is not None:
            status_row = session.exec(select(TaskStatus).where(TaskStatus.name == status)).first()
            if status_row is None:
                raise ValueError(f"Статус задачи не найден в справочнике TaskStatus: {status!r}")
            task.status_id = status_row.id

        task.completed = True
        task.date_finished = datetime.utcnow()
        session.add(task)
        session.commit()
        return {"id": task.id, "completed": task.completed, "date_finished": str(task.date_finished)}
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

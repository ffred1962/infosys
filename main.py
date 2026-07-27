from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Грузим .env раньше остальных импортов — core.auth читает SESSION_SECRET_KEY
# на импорте, а core.firm_search читает ANTHROPIC_API_KEY при каждом поиске.
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import logging

from api.plus import router as api_router
from api.task_status import router as api_task_status_router
from api.city import router as api_city_router
from api.firm_type import router as api_firm_type_router
from api.unit import router as api_unit_router
from api.constants import router as api_constants_router
from api.bug import router as api_bug_router
from api.admin_bug import router as api_admin_bug_router
from api.admin_notification import router as api_admin_notification_router
from api.task import router as api_task_router
from api.firm import router as api_firm_router
from api.mcp_server import mcp as infosys_mcp
from core.auth import SESSION_COOKIE_SECURE, SESSION_SECRET_KEY
from middlewares.no_cache import no_cache_admin_middleware
from middlewares.request_logging import request_logging_middleware
from routers.admin_auth import router as admin_auth_router
from routers.admin_usermgt import router as admin_usermgt_router
from routers.errors import http_exception_handler
from routers.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Обязателен для смонтированного MCP-моста (streamable HTTP) — session_manager.run()
    # поднимает фоновую task group, без которой любой MCP-запрос падает с
    # "session manager is not running".
    async with infosys_mcp.session_manager.run():
        yield


app = FastAPI(
    title="InfoSys API",
    description=(
        "Простое приложение на FastAPI с веб-страницами и API для арифметических операций. "
        "Документация доступна через Swagger UI и Redoc."
    ),
    version="0.1.0",
    contact={"name": "InfoSys Team", "email": "support@example.com"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Calculator", "description": "Операции над числами через REST API."},
    ],
    lifespan=lifespan,
)
# Configure basic logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# attach request logging middleware
app.middleware("http")(request_logging_middleware)
app.middleware("http")(no_cache_admin_middleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=None,
    https_only=SESSION_COOKIE_SECURE,
)
HOST = "127.0.0.1"
PORT = 8000
CSS_DIR = "CSS"
JS_DIR = "js"
app.mount("/CSS", StaticFiles(directory=str(CSS_DIR)), name="css")
app.mount("/js", StaticFiles(directory=str(JS_DIR)), name="js")

app.include_router(api_router)
app.include_router(api_task_status_router)
app.include_router(api_city_router)
app.include_router(api_firm_type_router)
app.include_router(api_unit_router)
app.include_router(api_constants_router)
app.include_router(api_bug_router)
app.include_router(api_admin_bug_router)
app.include_router(api_admin_notification_router)
app.include_router(api_task_router)
app.include_router(api_firm_router)
app.include_router(pages_router)
app.include_router(admin_auth_router)
app.include_router(admin_usermgt_router)
# MCP-мост для Claude (см. api/mcp_server.py) — смонтирован в КОРНЕ (не под
# префиксом типа /infosys_mcp), потому что OAuth-discovery-эндпоинты
# (/.well-known/oauth-authorization-server, /register и т.д.) по конвенции
# ищутся в корне origin'а — под префиксом Claude их не находил (см. историю
# правок). Обязательно регистрируется ПОСЛЕДНИМ: Mount("/", ...) матчит любой
# путь как префикс, так что если поставить его раньше — он перехватит вообще
# все запросы (включая "/", "/admin", "/crm" и т.д.) вместо реальных страниц;
# на этой позиции он получает только то, что не подошло ни одному более
# специфичному маршруту выше (сам мост живёт на /mcp, /authorize, /token,
# /register, /revoke, /oauth_login, /.well-known/... — ни один из них не
# пересекается с путями остального приложения). /oauth_login внутри моста
# переиспользует ту же сессионную cookie (SessionMiddleware) и no_cache-гейтинг,
# что и /admin*/crm* выше, никакой отдельной аутентификации на этом уровне не
# требуется.
app.mount("/", infosys_mcp.streamable_http_app())
app.add_exception_handler(404, http_exception_handler)


def main() -> None:
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    main()
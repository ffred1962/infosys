"""
Запрет кеширования браузером для аутентифицированных страниц (/admin, /crm)
и их JSON API (/api/admin/..., /api/task, /api/firm, /api/zakaz), а также MCP-моста для
Claude (api/mcp_server.py) — у него нет одного общего префикса (смонтирован в
корне ради OAuth-discovery, см. main.py), поэтому здесь перечислены его
конкретные пути по отдельности, а не один префикс типа /infosys_mcp.
"""

from fastapi import Request


NO_CACHE_PATH_PREFIXES = (
    "/admin",
    "/crm",
    "/api/admin",
    "/api/task",
    "/api/firm",
    "/api/zakaz",
    "/mcp",
    "/oauth_login",
    "/authorize",
    "/token",
    "/register",
    "/revoke",
    "/.well-known/oauth",
)


async def no_cache_admin_middleware(request: Request, call_next):
    """Без этих заголовков браузер может показать /admin* или /crm* из своего кеша
    (например, из истории/назад-вперёд), не выполняя реальный запрос к серверу —
    то есть в обход проверки сессии (и роли, для /admin) на каждый заход."""
    response = await call_next(request)
    if request.url.path.startswith(NO_CACHE_PATH_PREFIXES):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

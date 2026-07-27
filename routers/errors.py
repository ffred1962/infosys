from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.templates import templates


def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"title": "Страница не найдена", "active_page": ""},
            status_code=404,
        )

    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)
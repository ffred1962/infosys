from fastapi import Request

from views.base import render_page


def request_page(request: Request):
    client_host = request.client.host if request.client else "Неизвестно"

    return render_page(
        request,
        "request.html",
        "Информация из request",
        "request",
        {
            "client_host": client_host,
            "user_agent": request.headers.get("user-agent", "Неизвестно"),
            "accept_language": request.headers.get("accept-language", "Не указано"),
            "request_method": request.method,
            "request_url": str(request.url),
            "request_path": request.url.path,
            "request_query": request.url.query or "",
            "referrer": request.headers.get("referer", "Не указано"),
        },
    )
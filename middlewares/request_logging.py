import time
import logging

from fastapi import Request

logger = logging.getLogger("infosys.request")


async def request_logging_middleware(request: Request, call_next):
    """Middleware для логирования входящих HTTP-запросов.

    Логирует метод, путь, IP клиента, статус ответа и время обработки в миллисекундах.
    """
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        # позволяем ошибкам проброситься, но логируем их
        logger.exception(
            "Error handling request %s %s", request.method, request.url.path
        )
        raise
    finally:
        duration_ms = (time.time() - start) * 1000
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            "%s %s from %s -> %s (%.2fms)",
            request.method,
            request.url.path,
            client_host,
            getattr(response, "status_code", "-"),
            duration_ms,
        )

    return response

from typing import Any

from fastapi import Request

from core.templates import templates


def render_page(
    request: Request,
    template_name: str,
    title: str,
    active_page: str,
    extra_context: dict[str, Any] | None = None,
    status_code: int = 200,
):
    context = {
        "title": title,
        "active_page": active_page,
    }

    if extra_context is not None:
        context.update(extra_context)

    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
    )
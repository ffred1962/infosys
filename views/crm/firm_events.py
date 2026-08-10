import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.channel_type import ChannelType
from models.firm import Firm
from models.firm_channel import FirmChannel
from models.firm_event import FirmEvent
from models.users import User
from views.base import render_page


# Тот же признак безопасного relative-редиректа, что и в views/crm/firm_prices.py/
# firm_comments.py/firm_channels.py (не шарим приватный хелпер между модулями —
# см. паттерн _require_admin в api/*.py).
_SAFE_RETURN_RE = re.compile(r"^/(?!/|\\)")

PAGE_SIZE = 10


def _append_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _parse_positive_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 1 else None


def firm_events_page(
    request: Request,
    firm_id: int,
    page: Optional[str] = None,
    return_to: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(
            request, "admin/login.html", "Вход", "crm", {"next": f"/crm/firms/{firm_id}/events"}
        )

    firm = session.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Фирма не найдена.")

    page_num = _parse_positive_int(page) or 1

    total = session.exec(
        select(func.count())
        .select_from(FirmEvent)
        .join(FirmChannel, FirmChannel.id == FirmEvent.channel_id)
        .where(FirmChannel.firm_id == firm_id)
    ).one()
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page_num = min(max(page_num, 1), total_pages)

    rows = session.exec(
        select(FirmEvent, FirmChannel, ChannelType, User)
        .join(FirmChannel, FirmChannel.id == FirmEvent.channel_id)
        .join(ChannelType, ChannelType.id == FirmChannel.channel_id)
        .join(User, User.id == FirmEvent.user_id)
        .where(FirmChannel.firm_id == firm_id)
        .order_by(FirmEvent.created.desc(), FirmEvent.id.desc())
        .offset((page_num - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    events = [
        {"event": event, "channel": channel, "channel_type": channel_type, "author": author}
        for event, channel, channel_type, author in rows
    ]

    # Каналы связи этой фирмы — для <select> в форме добавления/редактирования
    # события (событие всегда привязано к конкретному каналу, не к фирме напрямую).
    channel_rows = session.exec(
        select(FirmChannel, ChannelType)
        .join(ChannelType, ChannelType.id == FirmChannel.channel_id)
        .where(FirmChannel.firm_id == firm_id)
        .order_by(ChannelType.name, FirmChannel.address)
    ).all()
    firm_channels = [{"id": ch.id, "label": f"{ct.name}: {ch.address}"} for ch, ct in channel_rows]

    safe_return = return_to if return_to and _SAFE_RETURN_RE.match(return_to) else "/crm/firms"
    close_url = _append_query_param(safe_return, "open_firm_id", str(firm_id))

    return render_page(
        request,
        "crm/firm_events.html",
        f"События: {firm.name}",
        "crm",
        {
            "firm": firm,
            "events": events,
            "firm_channels": firm_channels,
            "page": page_num,
            "total_pages": total_pages,
            "total": total,
            "close_url": close_url,
            "return_to": return_to or "",
        },
    )

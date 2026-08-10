import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access, user_has_role
from db.database import get_session
from models.channel_type import ChannelType
from models.firm import Firm
from models.firm_channel import FirmChannel
from views.base import render_page


# Тот же признак безопасного relative-редиректа, что и в views/crm/firm_prices.py/
# firm_comments.py (не шарим приватный хелпер между модулями — см. паттерн
# _require_admin в api/*.py).
_SAFE_RETURN_RE = re.compile(r"^/(?!/|\\)")


def _append_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def firm_channels_page(
    request: Request,
    firm_id: int,
    return_to: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(
            request, "admin/login.html", "Вход", "crm", {"next": f"/crm/firms/{firm_id}/channels"}
        )

    firm = session.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Фирма не найдена.")

    can_edit = firm.user_id == current_user.id or user_has_role(session, current_user.id, "admin")

    rows = session.exec(
        select(FirmChannel, ChannelType)
        .join(ChannelType, ChannelType.id == FirmChannel.channel_id)
        .where(FirmChannel.firm_id == firm_id)
        .order_by(FirmChannel.date_added.desc(), FirmChannel.id.desc())
    ).all()
    channels = [{"channel": ch, "channel_type": ct} for ch, ct in rows]

    # Тип канала задаётся только при создании — предлагаем только активные типы
    # (для уже существующих строк тип больше не редактируется инлайн, так что
    # полный список всех типов, включая деактивированные, здесь не нужен).
    active_channel_types = session.exec(
        select(ChannelType).where(ChannelType.is_active.is_(True)).order_by(ChannelType.name)
    ).all()

    safe_return = return_to if return_to and _SAFE_RETURN_RE.match(return_to) else "/crm/firms"
    close_url = _append_query_param(safe_return, "open_firm_id", str(firm_id))

    return render_page(
        request,
        "crm/firm_channels.html",
        f"Каналы связи: {firm.name}",
        "crm",
        {
            "firm": firm,
            "channels": channels,
            "active_channel_types": active_channel_types,
            "can_edit": can_edit,
            "close_url": close_url,
        },
    )

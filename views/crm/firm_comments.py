import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.firm import Firm
from models.firm_comment import FirmComment
from models.users import User
from views.base import render_page


# Тот же признак безопасного relative-редиректа, что и в views/crm/firm_prices.py
# (не шарим приватный хелпер между модулями — см. паттерн _require_admin в api/*.py).
_SAFE_RETURN_RE = re.compile(r"^/(?!/|\\)")


def _append_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def firm_comments_page(
    request: Request,
    firm_id: int,
    return_to: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(
            request, "admin/login.html", "Вход", "crm", {"next": f"/crm/firms/{firm_id}/comments"}
        )

    firm = session.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Фирма не найдена.")

    rows = session.exec(
        select(FirmComment, User.fullname)
        .join(User, User.id == FirmComment.user_id)
        .where(FirmComment.firm_id == firm_id)
        .order_by(FirmComment.added.desc(), FirmComment.id.desc())
    ).all()
    comments = [{"comment": c, "author_fullname": fullname} for c, fullname in rows]

    safe_return = return_to if return_to and _SAFE_RETURN_RE.match(return_to) else "/crm/firms"
    close_url = _append_query_param(safe_return, "open_firm_id", str(firm_id))

    return render_page(
        request,
        "crm/firm_comments.html",
        f"Примечания: {firm.name}",
        "crm",
        {"firm": firm, "comments": comments, "close_url": close_url},
    )

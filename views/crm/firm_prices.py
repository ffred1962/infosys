import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.firm import Firm
from models.firm_price import FirmPrice
from views.base import render_page


# Тот же признак безопасного relative-редиректа, что и _SAFE_NEXT_RE в
# views/admin/auth.py (не шарим приватный хелпер между модулями — см. паттерн
# _require_admin в api/*.py — но логика должна быть идентичной): один "/" не в
# начале двойного слэша и не за ним сразу бэкслэш, иначе браузер нормализует
# "/\evil.com" в протокол-относительный "//evil.com" (open redirect).
_SAFE_RETURN_RE = re.compile(r"^/(?!/|\\)")


def _append_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    # return_to может прийти от клиента уже содержащим свой собственный
    # open_firm_id (например, вручную собранная/забукмарченная ссылка) —
    # отбрасываем его, иначе получим два одноимённых параметра и
    # URLSearchParams.get() на стороне JS молча возьмёт чужой первый.
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def firm_prices_page(
    request: Request,
    firm_id: int,
    return_to: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(
            request, "admin/login.html", "Вход", "crm", {"next": f"/crm/firms/{firm_id}/prices"}
        )

    firm = session.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Фирма не найдена.")

    prices = session.exec(
        select(FirmPrice)
        .where(FirmPrice.firm_id == firm_id)
        .order_by(FirmPrice.created.desc(), FirmPrice.id.desc())
    ).all()

    # "Возврат" на список фирм должен попасть на ту же строку с той же
    # фильтрацией/страницей, откуда открыли карточку — а не на первую страницу
    # без фильтра. return_to несёт исходный /crm/firms?... в неизменном виде;
    # open_firm_id добавляется отдельно, чтобы js/firms.js переоткрыл карточку.
    safe_return = return_to if return_to and _SAFE_RETURN_RE.match(return_to) else "/crm/firms"
    close_url = _append_query_param(safe_return, "open_firm_id", str(firm_id))

    return render_page(
        request,
        "crm/firm_prices.html",
        f"Прайсы: {firm.name}",
        "crm",
        {"firm": firm, "prices": prices, "close_url": close_url},
    )

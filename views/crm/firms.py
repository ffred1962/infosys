from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access, user_has_role
from db.database import get_session
from models.city import City
from models.firm import Firm
from models.firm_type import FirmType
from models.users import User
from views.base import render_page


PAGE_SIZE = 10
PAGE_WINDOW = 2
MAX_QUERY_INT = 2_147_483_647


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_positive_int(value: Optional[str]) -> Optional[int]:
    """Разбирает id/page из query-параметра, отбрасывая пустые/некорректные/вне-диапазона
    значения — так пустая опция "Все города"/"Все типы" (value="") просто не применяет
    фильтр, а не падает ошибкой парсинга FastAPI."""
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    if parsed < 1 or parsed > MAX_QUERY_INT:
        return None
    return parsed


def firms_page(
    request: Request,
    city_id: Optional[str] = None,
    type_id: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "crm", {"next": "/crm/firms"})

    is_admin = user_has_role(session, current_user.id, "admin")

    city_id = _parse_positive_int(city_id)
    type_id = _parse_positive_int(type_id)
    page = _parse_positive_int(page) or 1
    q = q.strip() if q else None

    conditions = []
    if city_id is not None:
        conditions.append(Firm.city_id == city_id)
    if type_id is not None:
        conditions.append(Firm.type_id == type_id)
    if q:
        conditions.append(Firm.name.contains(_escape_like(q), escape="\\"))

    count_stmt = select(func.count()).select_from(Firm)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
    total = session.exec(count_stmt).one()

    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(max(page, 1), total_pages)

    Finder = aliased(User)
    data_stmt = (
        select(Firm, City.name, FirmType.name, Finder.fullname)
        .join(City, City.id == Firm.city_id)
        .join(FirmType, FirmType.id == Firm.type_id)
        .join(Finder, Finder.id == Firm.user_id)
    )
    for condition in conditions:
        data_stmt = data_stmt.where(condition)
    data_stmt = (
        data_stmt.order_by(Firm.creation_date.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    rows = session.exec(data_stmt).all()
    firms = [
        {
            "firm": firm,
            "city_name": city_name,
            "type_name": type_name,
            "finder_name": finder_name,
            "can_edit": is_admin or firm.user_id == current_user.id,
        }
        for firm, city_name, type_name, finder_name in rows
    ]

    cities = session.exec(select(City).order_by(City.name)).all()
    firm_types = session.exec(select(FirmType).order_by(FirmType.name)).all()

    filter_params = {}
    if city_id is not None:
        filter_params["city_id"] = city_id
    if type_id is not None:
        filter_params["type_id"] = type_id
    if q:
        filter_params["q"] = q
    filter_query = urlencode(filter_params)

    start_page = max(1, page - PAGE_WINDOW)
    end_page = min(total_pages, page + PAGE_WINDOW)
    page_numbers = list(range(start_page, end_page + 1))

    return render_page(
        request,
        "crm/firms.html",
        "Фирмы",
        "crm",
        {
            "firms": firms,
            "cities": cities,
            "firm_types": firm_types,
            "selected_city_id": city_id,
            "selected_type_id": type_id,
            "q": q or "",
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "page_numbers": page_numbers,
            "filter_query": filter_query,
        },
    )

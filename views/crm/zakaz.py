from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, Request
from sqlalchemy import func
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.city import City
from models.partner_application import PartnerApplication
from models.zakaz import Zakaz
from views.base import render_page


# Тот же фильтр+пагинация паттерн, что и views/crm/firms.py — глобальный
# список заказов (не привязан к одной фирме), доступен любому
# авторизованному пользователю, той же логикой, что и /crm/events.
PAGE_SIZE = 10
PAGE_WINDOW = 2
MAX_QUERY_INT = 2_147_483_647


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_positive_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    if parsed < 1 or parsed > MAX_QUERY_INT:
        return None
    return parsed


def _parse_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def zakaz_page(
    request: Request,
    city_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    num: Optional[str] = None,
    page: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "crm", {"next": "/crm/zakaz"})

    city_id_int = _parse_positive_int(city_id)
    date_from_parsed = _parse_date(date_from)
    date_to_parsed = _parse_date(date_to)
    page_num = _parse_positive_int(page) or 1
    q = q.strip() if q else None
    num = num.strip() if num else None

    conditions = []
    if city_id_int is not None:
        conditions.append(Zakaz.city_id == city_id_int)
    if date_from_parsed is not None:
        conditions.append(Zakaz.ord_date >= date_from_parsed)
    if date_to_parsed is not None:
        conditions.append(Zakaz.ord_date <= date_to_parsed)
    if num:
        conditions.append(Zakaz.num.contains(_escape_like(num), escape="\\"))
    if q:
        escaped = _escape_like(q)
        conditions.append(
            PartnerApplication.company_name.contains(escaped, escape="\\")
            | PartnerApplication.full_name.contains(escaped, escape="\\")
        )

    count_stmt = (
        select(func.count())
        .select_from(Zakaz)
        .join(PartnerApplication, PartnerApplication.id == Zakaz.anketa_id)
    )
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
    total = session.exec(count_stmt).one()

    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page_num = min(max(page_num, 1), total_pages)

    data_stmt = (
        select(Zakaz, PartnerApplication, City.name)
        .join(PartnerApplication, PartnerApplication.id == Zakaz.anketa_id)
        .join(City, City.id == Zakaz.city_id)
    )
    for condition in conditions:
        data_stmt = data_stmt.where(condition)
    data_stmt = (
        data_stmt.order_by(Zakaz.ord_date.desc(), Zakaz.id.desc())
        .offset((page_num - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    rows = session.exec(data_stmt).all()

    cities = session.exec(select(City).order_by(City.name)).all()
    city_name_by_id = {city.id: city.name for city in cities}

    # Анкеты собираем по уникальному id — на одной странице несколько заказов
    # часто принадлежат одному и тому же контрагенту (см. импорт из 1С), не
    # нужно рендерить по <template> с одинаковым содержимым на каждую строку.
    # anketa.city_id у импортированных анкет всегда пуст (импорт заполнял
    # только company_name/tax_id — см. CLAUDE.md), город заказа берётся из
    # самого Zakaz.city_id, но карточка анкеты всё равно резолвит city_id
    # так же, как admin/partner_applications.html — на случай будущих
    # анкет, где он окажется заполнен.
    anketas_by_id: dict[int, dict] = {}
    orders = []
    for zakaz, anketa, zakaz_city_name in rows:
        if anketa.id not in anketas_by_id:
            anketas_by_id[anketa.id] = {
                "id": anketa.id,
                "full_name": anketa.full_name,
                "phone": anketa.phone,
                "email": anketa.email,
                "company_name": anketa.company_name,
                "company_website": anketa.company_website,
                "activity_type": anketa.activity_type,
                "city_name": city_name_by_id.get(anketa.city_id) or anketa.city_other,
                "tax_id": anketa.tax_id,
                "comment": anketa.comment,
            }
        orders.append({
            "zakaz": zakaz,
            "anketa_id": anketa.id,
            "firm_name": anketa.company_name or anketa.full_name,
            "city_name": zakaz_city_name,
        })

    filter_params = {}
    if city_id_int is not None:
        filter_params["city_id"] = city_id_int
    if date_from_parsed is not None:
        filter_params["date_from"] = date_from_parsed.isoformat()
    if date_to_parsed is not None:
        filter_params["date_to"] = date_to_parsed.isoformat()
    if q:
        filter_params["q"] = q
    if num:
        filter_params["num"] = num
    filter_query = urlencode(filter_params)

    start_page = max(1, page_num - PAGE_WINDOW)
    end_page = min(total_pages, page_num + PAGE_WINDOW)
    page_numbers = list(range(start_page, end_page + 1))

    return render_page(
        request,
        "crm/zakaz.html",
        "Заказы",
        "crm",
        {
            "orders": orders,
            "anketas": list(anketas_by_id.values()),
            "cities": cities,
            "selected_city_id": city_id_int,
            "date_from": date_from_parsed.isoformat() if date_from_parsed else "",
            "date_to": date_to_parsed.isoformat() if date_to_parsed else "",
            "q": q or "",
            "num": num or "",
            "page": page_num,
            "total_pages": total_pages,
            "total": total,
            "page_numbers": page_numbers,
            "filter_query": filter_query,
        },
    )

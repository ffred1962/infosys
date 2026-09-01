"""
JSON API для заказов (Zakaz) — на сегодня один эндпоинт: отчёт по кнопке
"Анализ" на /crm/zakaz (js/zakaz.js). Любой авторизованный пользователь
(resolve_authenticated_access, как и сама страница /crm/zakaz), без
дополнительного гейтинга по роли — те же данные уже видны на самой странице.

Фильтрация заказов для анализа намеренно продублирована из
views/crm/zakaz.py:zakaz_page (тот же _escape_like/_parse_positive_int/
_parse_date) — тот же принцип, что и _require_admin в других api/*.py: мелкие
приватные хелперы в этом проекте копируются в каждый модуль, а не
выносятся в общий. Разница с views/crm/zakaz.py: здесь запрос НЕ
пагинируется — анализ должен смотреть на все строки, прошедшие фильтр, а не
только на текущую страницу.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from core.zakaz_analysis import ZakazRow, analyze_zakaz, serialize_categories
from db.database import get_session
from models.city import City
from models.partner_application import PartnerApplication
from models.users import User
from models.zakaz import Zakaz


router = APIRouter(prefix="/api/zakaz", tags=["Zakaz"])

MAX_QUERY_INT = 2_147_483_647


def _require_authenticated(request: Request, session: Session) -> User:
    state, current_user = resolve_authenticated_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Нужно войти в систему.")
    return current_user


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


@router.get("/analysis")
def analyze(
    request: Request,
    city_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    num: Optional[str] = None,
    session: Session = Depends(get_session),
):
    _require_authenticated(request, session)

    city_id_int = _parse_positive_int(city_id)
    date_from_parsed = _parse_date(date_from)
    date_to_parsed = _parse_date(date_to)
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

    data_stmt = (
        select(Zakaz, PartnerApplication, City.name)
        .join(PartnerApplication, PartnerApplication.id == Zakaz.anketa_id)
        .join(City, City.id == Zakaz.city_id)
    )
    for condition in conditions:
        data_stmt = data_stmt.where(condition)
    rows = session.exec(data_stmt).all()

    zakaz_rows = [
        ZakazRow(
            num=zakaz.num,
            ord_date=zakaz.ord_date,
            delivery_addr=zakaz.delivery_addr,
            city_name=city_name,
            anketa_id=anketa.id,
            firm_name=anketa.company_name or anketa.full_name,
        )
        for zakaz, anketa, city_name in rows
    ]

    categories = analyze_zakaz(zakaz_rows)

    return {
        "total_orders": len(zakaz_rows),
        "categories": serialize_categories(categories),
    }

from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.application_state import ApplicationState
from models.city import City
from models.firm_type import FirmType
from models.partner_application import PartnerApplication
from models.users import User
from views.base import render_page


# Отдельный алиас на User — verified_by ссылается на ту же таблицу user, что
# и обычный логин, aliased() нужен ровно по той же причине, что и в
# views/crm/events.py/views/admin/notifications.py (два независимых join'а на
# один и тот же user были бы неоднозначны без алиаса).
VerifierUser = aliased(User)


# Тот же паттерн фильтр+пагинация, что и views/crm/firms.py — просмотр анкет,
# как и попросил пользователь, "как у списка фирм": таблица с фильтром и
# постраничной навигацией, клик по имени/компании открывает саму анкету.
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


def partner_applications_page(
    request: Request,
    claimed_type_id: Optional[str] = None,
    status_id: Optional[str] = None,
    city_id: Optional[str] = None,
    q: Optional[str] = None,
    page: Optional[str] = None,
    session: Session = Depends(get_session),
):
    state, current_user = resolve_admin_access(request, session)

    if state == "setup":
        return render_page(request, "admin/setup.html", "Создание администратора", "admin")
    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "admin")
    if state == "forbidden":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")

    claimed_type_id_int = _parse_positive_int(claimed_type_id)
    status_id_int = _parse_positive_int(status_id)
    city_id_int = _parse_positive_int(city_id)
    page_num = _parse_positive_int(page) or 1
    q = q.strip() if q else None

    conditions = []
    if claimed_type_id_int is not None:
        conditions.append(PartnerApplication.claimed_type_id == claimed_type_id_int)
    if status_id_int is not None:
        conditions.append(PartnerApplication.status_id == status_id_int)
    if city_id_int is not None:
        conditions.append(PartnerApplication.city_id == city_id_int)
    if q:
        escaped = _escape_like(q)
        conditions.append(
            PartnerApplication.full_name.contains(escaped, escape="\\")
            | PartnerApplication.company_name.contains(escaped, escape="\\")
        )

    count_stmt = select(func.count()).select_from(PartnerApplication)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
    total = session.exec(count_stmt).one()

    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page_num = min(max(page_num, 1), total_pages)

    # LEFT JOIN на City — city_id может быть NULL (заявитель указал город
    # текстом, см. city_other), inner join такие строки бы просто скрыл.
    # claimed_type_id/status_id у анкеты всегда заполнены (обе NOT NULL), так
    # что обычный join по ним ничего не потеряет. VerifierUser — тоже LEFT
    # JOIN: verified_by пустой у ещё не проверенных анкет.
    data_stmt = (
        select(PartnerApplication, City.name, FirmType.name, ApplicationState.name, VerifierUser.email)
        .join(City, City.id == PartnerApplication.city_id, isouter=True)
        .join(FirmType, FirmType.id == PartnerApplication.claimed_type_id)
        .join(ApplicationState, ApplicationState.id == PartnerApplication.status_id)
        .join(VerifierUser, VerifierUser.id == PartnerApplication.verified_by, isouter=True)
    )
    for condition in conditions:
        data_stmt = data_stmt.where(condition)
    data_stmt = (
        data_stmt.order_by(PartnerApplication.created.desc())
        .offset((page_num - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    rows = session.exec(data_stmt).all()
    applications = [
        {
            "application": app,
            "city_name": city_name,
            "type_name": type_name,
            "state_name": state_name,
            "verifier_email": verifier_email,
        }
        for app, city_name, type_name, state_name, verifier_email in rows
    ]

    cities = session.exec(select(City).order_by(City.name)).all()
    firm_types = session.exec(select(FirmType).order_by(FirmType.name)).all()
    application_states = session.exec(select(ApplicationState).order_by(ApplicationState.id)).all()

    filter_params = {}
    if claimed_type_id_int is not None:
        filter_params["claimed_type_id"] = claimed_type_id_int
    if status_id_int is not None:
        filter_params["status_id"] = status_id_int
    if city_id_int is not None:
        filter_params["city_id"] = city_id_int
    if q:
        filter_params["q"] = q
    filter_query = urlencode(filter_params)

    start_page = max(1, page_num - PAGE_WINDOW)
    end_page = min(total_pages, page_num + PAGE_WINDOW)
    page_numbers = list(range(start_page, end_page + 1))

    return render_page(
        request,
        "admin/partner_applications.html",
        "Анкеты партнёров",
        "admin",
        {
            "applications": applications,
            "cities": cities,
            "firm_types": firm_types,
            "application_states": application_states,
            "selected_claimed_type_id": claimed_type_id_int,
            "selected_status_id": status_id_int,
            "selected_city_id": city_id_int,
            "q": q or "",
            "page": page_num,
            "total_pages": total_pages,
            "total": total,
            "page_numbers": page_numbers,
            "filter_query": filter_query,
        },
    )

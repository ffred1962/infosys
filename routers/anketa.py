"""
POST-обработчик публичной анкеты партнёра (см. views/anketa.py за GET-страницей
/anketa). Отдельный APIRouter, а не PageRoute — тот же паттерн, что и
routers/admin_auth.py: PAGE_ROUTES в routers/pages.py по конвенции только
GET-роуты.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from db.database import get_session
from models.application_state import ApplicationState
from models.city import City
from models.firm_type import FirmType
from models.notification import Notification
from models.partner_application import CUSTOMER_SEGMENT_OPTIONS, PartnerApplication
from models.role import Role
from models.user_role import UserRole
from views.base import render_page


logger = logging.getLogger("infosys.routers.anketa")

router = APIRouter()

# Верхняя граница разумного значения id из form-параметра — тот же приём, что
# и _parse_positive_int в views/crm/firms.py/views/admin/partner_applications.py,
# продублирован здесь (см. конвенцию проекта: небольшие приватные хелперы не
# шарятся между модулями), потому что это единственное место в проекте, где
# такой парсинг делает ПОЛНОСТЬЮ неаутентифицированный вызывающий: без верхней
# границы `int("99999999999999999999")` разбирается без ValueError (у Python
# целые произвольной точности), а дальше падает необработанным OverflowError
# на SQLite / "OutOfRange" на Postgres при попытке привязать его к запросу.
MAX_QUERY_INT = 2_147_483_647

# Название состояния, проставляемого новой анкете автоматически — сама анкета
# не даёт заявителю выбирать статус рассмотрения, это исключительно внутреннее
# поле (см. models/application_state.py, заполняется миграцией).
DEFAULT_APPLICATION_STATE_NAME = "новая"

# Разумные предельные длины полей — на этой странице (в отличие от всех
# остальных мест этого проекта, кроме BugReportIn.title) ввод принимает
# ПОЛНОСТЬЮ неаутентифицированного посетителя, без сессии/CSRF/лимита частоты
# запросов, так что без ограничения по размеру сюда можно бесконечно слать
# огромные значения полей. (label, form-ключ, макс. длина).
_LENGTH_LIMITS = (
    ("ФИО", "full_name", 200),
    ("Телефон", "phone", 50),
    ("Email", "email", 200),
    ("Название компании", "company_name", 200),
    ("Сайт компании", "company_website", 500),
    ("Чем вы занимаетесь", "activity_type", 300),
    ("Город", "city_other", 200),
    ("Количество проектов", "projects_count", 100),
    ("Описание проектов", "projects_description", 3000),
    ("Сегмент клиентов", "customer_segment", 100),
    ("Instagram", "instagram", 300),
    ("Facebook", "facebook", 300),
    ("LinkedIn", "linkedin", 300),
    ("Лет на рынке", "years_in_business", 100),
    ("Количество сотрудников", "team_size", 100),
    ("Бренды дверей", "current_brands", 500),
    ("ИНН/ОКПО", "tax_id", 50),
    ("Комментарий", "comment", 5000),
)

# Технические поля запроса (client_ip/user_agent) — тоже приходят от
# неаутентифицированного клиента (заголовок User-Agent целиком под его
# контролем), поэтому молча обрезаем, а не отклоняем — тот же приём и то же
# число, что и core.auth.MAX_LOGIN_INFO_FIELD_LENGTH для login_info.
MAX_REQUEST_FIELD_LENGTH = 500


def _render_anketa_form(request: Request, session: Session, error: str, fields: dict, status_code: int = 400):
    cities = session.exec(select(City).order_by(City.name)).all()
    firm_types = session.exec(select(FirmType).order_by(FirmType.name)).all()
    context = {
        "cities": cities,
        "firm_types": firm_types,
        "customer_segment_options": CUSTOMER_SEGMENT_OPTIONS,
        "submitted": False,
        "error": error,
    }
    context.update(fields)
    return render_page(
        request, "anketa.html", "Анкета партнёра", "anketa", context, status_code=status_code
    )


def _tristate(value: str) -> Optional[bool]:
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def _parse_bounded_id(raw: str) -> Optional[int]:
    """int(raw), но с верхней/нижней границей — см. MAX_QUERY_INT выше. None
    для пустого/нечислового/вне-диапазона значения, а не исключение."""
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    if parsed <= 0 or parsed > MAX_QUERY_INT:
        return None
    return parsed


def _get_default_application_state_id(session: Session) -> int:
    state = session.exec(
        select(ApplicationState).where(ApplicationState.name == DEFAULT_APPLICATION_STATE_NAME)
    ).first()
    if state is None:
        # Отсутствие сид-данных — ошибка конфигурации сервера, а не ввода
        # заявителя, поэтому не рендерим форму заново, а честно 500-им, как
        # api/firm.py делает при отсутствующей единице измерения по умолчанию.
        raise HTTPException(
            status_code=500,
            detail=f'Не найден статус анкеты по умолчанию ("{DEFAULT_APPLICATION_STATE_NAME}") — обратитесь к администратору.',
        )
    return state.id


# Form("") везде, где дальше есть собственная проверка на пустоту — тот же
# паттерн, что и в views/admin/usermgt.py (Starlette иначе отбрасывает
# form-поле целиком при пустой строке и роут падает 422 ДО этой проверки).
@router.post("/anketa/submit")
def submit_anketa(
    request: Request,
    full_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    claimed_type_id: str = Form(""),
    company_name: str = Form(""),
    company_website: str = Form(""),
    activity_type: str = Form(""),
    city_id: str = Form(""),
    city_other: str = Form(""),
    has_physical_office: str = Form(""),
    projects_description: str = Form(""),
    projects_count: str = Form(""),
    customer_segment: str = Form(""),
    instagram: str = Form(""),
    facebook: str = Form(""),
    linkedin: str = Form(""),
    years_in_business: str = Form(""),
    team_size: str = Form(""),
    current_brands: str = Form(""),
    tax_id: str = Form(""),
    wants_discount: Optional[str] = Form(None),
    wants_sample: Optional[str] = Form(None),
    comment: str = Form(""),
    hp_x92q: str = Form(""),  # honeypot — см. templates/anketa.html, реальный посетитель его не видит/не заполняет
    session: Session = Depends(get_session),
):
    if hp_x92q.strip():
        # Похоже на бота — молча притворяемся успехом, ничего не создавая и
        # не сохраняя, и не показываем боту, что его распознали (честная
        # ошибка подсказала бы, какое поле нужно оставлять пустым). Но
        # логируем сам факт срабатывания (с IP/UA) — иначе ложные срабатывания
        # (например, агрессивный автозаполнитель браузера у реального
        # посетителя) были бы никому не видны и заявитель молча терял бы
        # анкету без единого следа в системе.
        logger.warning(
            "Anketa submission discarded as spam (honeypot filled): ip=%s ua=%s",
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", ""),
        )
        return RedirectResponse(url="/anketa?submitted=1", status_code=303)

    full_name = full_name.strip()
    phone = phone.strip()
    email = email.strip()
    company_name = company_name.strip()
    company_website = company_website.strip()
    activity_type = activity_type.strip()
    city_other = city_other.strip()
    projects_description = projects_description.strip()
    projects_count = projects_count.strip()
    instagram = instagram.strip()
    facebook = facebook.strip()
    linkedin = linkedin.strip()
    years_in_business = years_in_business.strip()
    team_size = team_size.strip()
    current_brands = current_brands.strip()
    tax_id = tax_id.strip()
    comment = comment.strip()

    # Ровно те же ключи, что views/anketa.py:_BLANK_FIELDS — чтобы повторно
    # отрисованная форма показала введённое, а не откатилась к пустой.
    fields = {
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "selected_claimed_type_id": claimed_type_id,
        "company_name": company_name,
        "company_website": company_website,
        "activity_type": activity_type,
        "selected_city_id": city_id,
        "city_other": city_other,
        "has_physical_office_value": has_physical_office,
        "projects_description": projects_description,
        "projects_count": projects_count,
        "customer_segment": customer_segment,
        "instagram": instagram,
        "facebook": facebook,
        "linkedin": linkedin,
        "years_in_business": years_in_business,
        "team_size": team_size,
        "current_brands": current_brands,
        "tax_id": tax_id,
        "wants_discount_checked": bool(wants_discount),
        "wants_sample_checked": bool(wants_sample),
        "comment": comment,
    }

    if not full_name:
        return _render_anketa_form(request, session, "Укажите ваше ФИО.", fields)
    if not phone:
        return _render_anketa_form(request, session, "Укажите телефон.", fields)

    for label, key, max_length in _LENGTH_LIMITS:
        if len(fields[key]) > max_length:
            return _render_anketa_form(
                request, session, f'Поле "{label}" слишком длинное (максимум {max_length} символов).', fields
            )

    claimed_type_id_int = _parse_bounded_id(claimed_type_id)
    if claimed_type_id_int is None or session.get(FirmType, claimed_type_id_int) is None:
        return _render_anketa_form(request, session, "Выберите ваш тип из списка.", fields)

    city_id_int = _parse_bounded_id(city_id)
    # Несуществующий id молча игнорируем (не 500-им на нём) — если заявленный
    # город не находится в справочнике, ниже сработает проверка "город не
    # указан вообще", а не невнятная ошибка про id.
    if city_id_int is not None and session.get(City, city_id_int) is None:
        city_id_int = None

    if city_id_int is None and not city_other:
        return _render_anketa_form(request, session, "Укажите город.", fields)

    application = PartnerApplication(
        full_name=full_name,
        phone=phone,
        email=email or None,
        claimed_type_id=claimed_type_id_int,
        company_name=company_name or None,
        company_website=company_website or None,
        activity_type=activity_type or None,
        city_id=city_id_int,
        # city_other сохраняем только если реальный справочный город не выбран
        # — иначе при city_id_int заполненном это поле просто мусор.
        city_other=(city_other or None) if city_id_int is None else None,
        has_physical_office=_tristate(has_physical_office),
        projects_description=projects_description or None,
        projects_count=projects_count or None,
        customer_segment=customer_segment or None,
        instagram=instagram or None,
        facebook=facebook or None,
        linkedin=linkedin or None,
        years_in_business=years_in_business or None,
        team_size=team_size or None,
        current_brands=current_brands or None,
        tax_id=tax_id or None,
        wants_discount=bool(wants_discount),
        wants_sample=bool(wants_sample),
        comment=comment or None,
        status_id=_get_default_application_state_id(session),
        # Тот же fallback-приём, что и middlewares/request_logging.py и
        # core.auth.record_login_attempt — request.client может быть None
        # (например, в некоторых тестовых транспортах).
        client_ip=(request.client.host if request.client else "unknown")[:MAX_REQUEST_FIELD_LENGTH],
        user_agent=request.headers.get("user-agent", "")[:MAX_REQUEST_FIELD_LENGTH] or None,
    )
    session.add(application)
    session.flush()  # получаем application.id для текста уведомления, коммитим всё одним махом ниже

    # Уведомляем всех админов о новой анкете — тот же fan-out, что и
    # api/bug.py:report_bug. Заявка полностью неаутентифицированная, реального
    # User-отправителя нет, так что creator_id уведомления = сам получатель
    # (creator_id == receiver_id) — не хак, тот же случай, что CLAUDE.md уже
    # описывает для баг-репортов ("админ, репортящий свой баг, тоже получает
    # уведомление"), просто здесь единственный доступный вариант, а не один из.
    admin_ids = session.exec(
        select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.name == "admin")
    ).all()
    applicant_label = company_name or full_name
    notify_msg = f"Новая анкета партнёра #{application.id} от {applicant_label} ({phone})"
    for admin_id in admin_ids:
        session.add(Notification(creator_id=admin_id, receiver_id=admin_id, msg=notify_msg))

    session.commit()

    return RedirectResponse(url="/anketa?submitted=1", status_code=303)

"""
Публичная анкета потенциального партнёра — /anketa, без входа в систему (не
использует resolve_authenticated_access/resolve_admin_access, в отличие от
всех остальных страниц: любой человек по прямой ссылке). См.
models/partner_application.py и routers/anketa.py (обработчик POST).
"""

from fastapi import Depends, Request
from sqlmodel import Session, select

from db.database import get_session
from models.city import City
from models.firm_type import FirmType
from models.partner_application import CUSTOMER_SEGMENT_OPTIONS
from views.base import render_page


# Значения полей формы по умолчанию для чистого открытия страницы (без ошибки
# валидации) — тот же набор ключей, что routers/anketa.py:submit_anketa
# подставляет при повторной отрисовке формы с уже введёнными значениями после
# неудачной валидации, чтобы шаблону не приходилось гадать про отсутствующие
# переменные.
_BLANK_FIELDS = {
    "full_name": "",
    "phone": "",
    "email": "",
    "selected_claimed_type_id": "",
    "company_name": "",
    "company_website": "",
    "activity_type": "",
    "selected_city_id": "",
    "city_other": "",
    "has_physical_office_value": "",
    "projects_description": "",
    "projects_count": "",
    "customer_segment": "",
    "instagram": "",
    "facebook": "",
    "linkedin": "",
    "years_in_business": "",
    "team_size": "",
    "current_brands": "",
    "tax_id": "",
    "wants_discount_checked": False,
    "wants_sample_checked": False,
    "comment": "",
}


def anketa_page(request: Request, session: Session = Depends(get_session)):
    cities = session.exec(select(City).order_by(City.name)).all()
    firm_types = session.exec(select(FirmType).order_by(FirmType.name)).all()
    submitted = request.query_params.get("submitted") == "1"

    context = {
        "cities": cities,
        "firm_types": firm_types,
        "customer_segment_options": CUSTOMER_SEGMENT_OPTIONS,
        "submitted": submitted,
        "error": None,
    }
    context.update(_BLANK_FIELDS)

    return render_page(request, "anketa.html", "Анкета партнёра", "anketa", context)

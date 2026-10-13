"""
Тесты для фич "сегмент рынка" (market_segments, несколько значений) и
"ценовой сегмент" (customer_segment, переименован из "сегмент клиентов") на
публичной анкете /anketa — см. CLAUDE.md, раздел "Partner application
questionnaire" / "Price segment vs. market segment".

Следует тому же паттерну, что и tests/test_api_plus.py: `from main import app`
(загружает .env) + `fastapi.testclient.TestClient` против настоящего app, без
моков. Пишет настоящие строки в БД (через POST /anketa/submit и напрямую через
db.database.engine) и удаляет их после каждого теста — проект требует не
оставлять тестовые данные ни в data/infosys.db, ни в реальном Postgres.
"""

import re
import uuid

from fastapi.testclient import TestClient

# Импорт main первым — грузит .env до импорта остальных модулей проекта.
from main import app

from core.auth import hash_password
from db.database import engine
from models.application_state import ApplicationState
from models.firm_type import FirmType
from models.login_info import LoginInfo
from models.partner_application import (
    CUSTOMER_SEGMENT_OPTIONS,
    MARKET_SEGMENT_OPTIONS,
    PartnerApplication,
)
from models.role import Role
from models.user_role import UserRole
from models.users import User
from sqlmodel import Session, select


client = TestClient(app)


# --------------------------------------------------------------------------
# Общие хелперы
# --------------------------------------------------------------------------


def _existing_firm_type_id() -> int:
    with Session(engine) as session:
        row = session.exec(select(FirmType).order_by(FirmType.id)).first()
        assert row is not None, "ожидается хотя бы одна существующая строка firm_type"
        return row.id


def _default_application_state_id() -> int:
    with Session(engine) as session:
        row = session.exec(select(ApplicationState).where(ApplicationState.name == "новая")).first()
        assert row is not None, 'ожидается сид-строка application_states.name == "новая"'
        return row.id


def _delete_application(app_id: int) -> None:
    with Session(engine) as session:
        row = session.get(PartnerApplication, app_id)
        if row is not None:
            session.delete(row)
            session.commit()


def _find_application_by_full_name(full_name: str) -> PartnerApplication:
    with Session(engine) as session:
        rows = session.exec(
            select(PartnerApplication).where(PartnerApplication.full_name == full_name)
        ).all()
        assert len(rows) == 1, f"ожидалась ровно одна анкета с full_name={full_name!r}, найдено {len(rows)}"
        return rows[0]


def _unique_marker(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


FIRM_TYPE_ID = _existing_firm_type_id()


def _base_form(marker: str) -> dict:
    return {
        "full_name": marker,
        "phone": "+380000000001",
        "claimed_type_id": str(FIRM_TYPE_ID),
        "city_other": "Тестовый город",
    }


# --------------------------------------------------------------------------
# 1. GET /anketa — label text + checkboxes
# --------------------------------------------------------------------------


def test_anketa_page_shows_relabeled_price_segment_text():
    resp = client.get("/anketa")
    assert resp.status_code == 200
    assert "Ценовой сегмент" in resp.text
    assert "Сегмент ваших клиентов" not in resp.text
    assert "Сегмент клиентов" not in resp.text


def test_anketa_page_renders_all_market_segment_checkboxes_unchecked():
    resp = client.get("/anketa")
    assert resp.status_code == 200

    checkbox_tags = re.findall(r'<input[^>]*name="market_segments"[^>]*>', resp.text)
    assert len(checkbox_tags) == len(MARKET_SEGMENT_OPTIONS) == 8

    for option in MARKET_SEGMENT_OPTIONS:
        assert f'value="{option}"' in resp.text

    for tag in checkbox_tags:
        assert "checked" not in tag


# --------------------------------------------------------------------------
# 2. POST /anketa/submit — valid + tampered market_segments
# --------------------------------------------------------------------------


def test_submit_filters_tampered_and_reorders_to_canonical_order():
    marker = _unique_marker("ms-valid-tampered")
    data = _base_form(marker)
    comma_option = "HoReCa (гостиницы, рестораны)"  # содержит запятую в самом тексте опции
    first_option = "Новостройки (жильё)"  # MARKET_SEGMENT_OPTIONS[0]
    assert MARKET_SEGMENT_OPTIONS.index(first_option) < MARKET_SEGMENT_OPTIONS.index(comma_option)

    data["market_segments"] = [
        comma_option,
        "ПОДДЕЛАННЫЙ_НЕСУЩЕСТВУЮЩИЙ_ВАРИАНТ",
        first_option,
    ]

    resp = client.post("/anketa/submit", data=data, follow_redirects=False)
    assert resp.status_code == 303

    row = _find_application_by_full_name(marker)
    try:
        assert row.market_segments == f"{first_option}|{comma_option}"
    finally:
        _delete_application(row.id)


# --------------------------------------------------------------------------
# 3. POST /anketa/submit — zero market_segments -> NULL, not ""
# --------------------------------------------------------------------------


def test_submit_with_no_market_segments_stores_null():
    marker = _unique_marker("ms-none")
    data = _base_form(marker)

    resp = client.post("/anketa/submit", data=data, follow_redirects=False)
    assert resp.status_code == 303

    row = _find_application_by_full_name(marker)
    try:
        assert row.market_segments is None
    finally:
        _delete_application(row.id)


# --------------------------------------------------------------------------
# 4. POST /anketa/submit — duplicate values for the same option -> stored once
# --------------------------------------------------------------------------


def test_submit_with_duplicate_market_segment_values_stores_once():
    marker = _unique_marker("ms-dup")
    data = _base_form(marker)
    option = "Частные дома и коттеджи"

    data["market_segments"] = [option, option]

    resp = client.post("/anketa/submit", data=data, follow_redirects=False)
    assert resp.status_code == 303

    row = _find_application_by_full_name(marker)
    try:
        assert row.market_segments == option
    finally:
        _delete_application(row.id)


# --------------------------------------------------------------------------
# 5. Validation failure re-render keeps checkboxes checked
# --------------------------------------------------------------------------


def test_validation_failure_rerenders_with_checked_market_segments():
    checked_option = "Промышленные объекты"
    unchecked_option = "Госсектор / бюджетные объекты"

    form_data = {
        "full_name": "",  # пустое -> отклоняется до создания строки в БД
        "phone": "+380000000002",
        "claimed_type_id": str(FIRM_TYPE_ID),
        "city_other": "Тестовый город",
        "market_segments": [checked_option],
    }

    resp = client.post("/anketa/submit", data=form_data, follow_redirects=False)
    assert resp.status_code == 400
    assert "Укажите ваше ФИО." in resp.text

    checkbox_tags = re.findall(r'<input[^>]*name="market_segments"[^>]*>', resp.text)
    assert len(checkbox_tags) == len(MARKET_SEGMENT_OPTIONS)

    checked_tag = next(t for t in checkbox_tags if f'value="{checked_option}"' in t)
    assert "checked" in checked_tag

    unchecked_tag = next(t for t in checkbox_tags if f'value="{unchecked_option}"' in t)
    assert "checked" not in unchecked_tag


# --------------------------------------------------------------------------
# 6. customer_segment validation (bug-fixer pass) — valid kept, tampered -> NULL
# --------------------------------------------------------------------------


def test_submit_with_valid_customer_segment_is_stored_as_is():
    marker = _unique_marker("cs-valid")
    data = _base_form(marker)
    data["customer_segment"] = "Эконом"
    assert "Эконом" in CUSTOMER_SEGMENT_OPTIONS

    resp = client.post("/anketa/submit", data=data, follow_redirects=False)
    assert resp.status_code == 303

    row = _find_application_by_full_name(marker)
    try:
        assert row.customer_segment == "Эконом"
    finally:
        _delete_application(row.id)


def test_submit_with_tampered_customer_segment_is_stored_as_null():
    marker = _unique_marker("cs-tampered")
    data = _base_form(marker)
    data["customer_segment"] = "ПОДДЕЛАННЫЙ_НЕСУЩЕСТВУЮЩИЙ_СЕГМЕНТ"

    resp = client.post("/anketa/submit", data=data, follow_redirects=False)
    assert resp.status_code == 303

    row = _find_application_by_full_name(marker)
    try:
        assert row.customer_segment is None
    finally:
        _delete_application(row.id)


# --------------------------------------------------------------------------
# 7. Admin card display — "; " join, not a bare ","
# --------------------------------------------------------------------------


def test_admin_card_joins_market_segments_with_semicolon():
    marker = _unique_marker("admin-ms")
    first_option = "Новостройки (жильё)"
    comma_option = "HoReCa (гостиницы, рестораны)"

    application = PartnerApplication(
        full_name=marker,
        phone="+380000000003",
        claimed_type_id=FIRM_TYPE_ID,
        market_segments=f"{first_option}|{comma_option}",
        status_id=_default_application_state_id(),
    )

    admin_email = f"{_unique_marker('admin-ms-user')}@example.com".lower()
    admin_password = "temp-password-12345"
    app_id = None
    user_id = None
    admin_role_id = None

    try:
        with Session(engine) as session:
            session.add(application)
            session.commit()
            session.refresh(application)
            app_id = application.id

            admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
            assert admin_role is not None, 'ожидается сид-роль "admin"'
            admin_role_id = admin_role.id

            user = User(
                email=admin_email,
                fullname="Temp Market Segment Admin",
                name="tempmsadmin",
                passwordhash=hash_password(admin_password),
                isactive=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id

            session.add(UserRole(user_id=user_id, role_id=admin_role_id))
            session.commit()

        login_resp = client.post(
            "/admin/login",
            data={"email": admin_email, "password": admin_password, "next": "/admin"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303

        resp = client.get("/admin/partner_applications")
        assert resp.status_code == 200

        expected = f"{first_option}; {comma_option}"
        assert expected in resp.text
    finally:
        if app_id is not None:
            _delete_application(app_id)
        with Session(engine) as session:
            if user_id is not None:
                for row in session.exec(select(LoginInfo).where(LoginInfo.user_id == user_id)).all():
                    session.delete(row)
                if admin_role_id is not None:
                    ur = session.get(UserRole, (user_id, admin_role_id))
                    if ur is not None:
                        session.delete(ur)
                user_row = session.get(User, user_id)
                if user_row is not None:
                    session.delete(user_row)
            session.commit()

"""
JSON API для рассмотрения анкеты партнёра (используется JS на странице
/admin/partner_applications). Тот же admin-gated AJAX-паттерн, что и
api/admin_bug.py — два действия: сохранить статус рассмотрения и внутренние
заметки проверки одной формой (PATCH .../review) и запустить AI-анализ анкеты с
дозаписью отчёта в заметки (POST .../analyze). Никакого создания/удаления анкет
через этот API нет — анкеты создаются только публичной формой /anketa/submit.
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.auth import resolve_admin_access
from core.partner_analysis import PartnerAnalysisError, analyze_application
from db.database import IS_SQLITE, get_session
from models.application_state import ApplicationState
from models.city import City
from models.firm_type import FirmType
from models.partner_application import PartnerApplication
from models.users import User


logger = logging.getLogger("infosys.api.admin_partner_applications")

router = APIRouter(prefix="/api/admin/partner_applications", tags=["Admin - Анкеты партнёров"])

# Заметки проверки — внутреннее поле, но всё равно admin-only ввод без явной
# верхней границы был бы небрежностью (тот же принцип, что и _LENGTH_LIMITS в
# routers/anketa.py, просто здесь не единственная защита — вызывающий уже
# аутентифицирован и admin-gated). Лимит поднят с 5000 до 20000, когда сюда
# начали дописываться отчёты AI-анализа (см. analyze_application_endpoint) —
# один отчёт занимает 1–3 тыс. символов, а прогонов на анкету может быть
# несколько.
MAX_VERIFICATION_NOTES_LENGTH = 20000
# Меньше этого места под новый отчёт после вызова — нет смысла дописывать
# обрезок (жёсткий пол); а ДО платного вызова требуем запас побольше, под
# реальный размер отчёта (обычно 1–4 тыс. символов, длина текстов модели в нём
# ограничена в core/partner_analysis.py) — иначе можно заплатить за анализ и
# получить 400.
MIN_REPORT_ROOM = 300
PRECHECK_REPORT_ROOM = 6000

# Анкеты, которые анализируются прямо сейчас (в этом процессе): защита от
# двойного клика/второго админа/повторного открытия карточки — второй платный
# анализ той же анкеты не запускается. Состояние только в памяти процесса, как
# и остальные "живые" структуры в проекте (MCP OAuth-провайдер); при
# нескольких воркерах защита частичная — для демо-масштаба достаточно.
_analysis_lock = threading.Lock()
_analysis_in_progress: set[int] = set()


def _require_admin(request: Request, session: Session) -> User:
    state, current_user = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")
    return current_user


class ReviewIn(BaseModel):
    status_id: int
    verification_notes: Optional[str] = Field(default=None, max_length=MAX_VERIFICATION_NOTES_LENGTH)


class ReviewOut(BaseModel):
    id: int
    status_id: int
    state_name: str
    verification_notes: Optional[str]
    verified_by: Optional[int]
    verifier_email: Optional[str]
    last_changed: datetime


@router.patch("/{application_id}/review", response_model=ReviewOut)
def review_application(
    application_id: int,
    payload: ReviewIn,
    request: Request,
    session: Session = Depends(get_session),
) -> ReviewOut:
    current_user = _require_admin(request, session)

    application = session.get(PartnerApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Анкета не найдена.")

    state = session.get(ApplicationState, payload.status_id)
    if state is None:
        raise HTTPException(status_code=422, detail="Неизвестный статус рассмотрения.")

    notes = payload.verification_notes.strip() if payload.verification_notes else None

    application.status_id = state.id
    application.verification_notes = notes or None
    # verified_by/last_changed — только сервером, никогда с клиента: любое
    # сохранение этой формы и есть факт "кто-то проверил анкету сейчас".
    application.verified_by = current_user.id
    application.last_changed = datetime.utcnow()
    session.add(application)
    session.commit()
    session.refresh(application)

    return ReviewOut(
        id=application.id,
        status_id=application.status_id,
        state_name=state.name,
        verification_notes=application.verification_notes,
        verified_by=application.verified_by,
        verifier_email=current_user.email,
        last_changed=application.last_changed,
    )


class AnalyzeIn(BaseModel):
    # Текущее содержимое поля "Заметки проверки" в карточке — может содержать
    # ещё не сохранённые правки админа; отчёт дописывается именно к нему, а не
    # к значению в БД, чтобы не затереть набранное, но не сохранённое.
    verification_notes: Optional[str] = Field(default=None, max_length=MAX_VERIFICATION_NOTES_LENGTH)
    # last_changed анкеты, который карточка видела при открытии (ISO из
    # атрибута кнопки). Если в БД уже другое значение — заметки успели
    # изменить в другом месте, и дописывать отчёт к устаревшей копии из
    # браузера нельзя (см. analyze_application_endpoint).
    last_changed_seen: Optional[datetime] = None


class AnalyzeOut(BaseModel):
    verification_notes: str
    last_changed: datetime


def _room_for_report(existing_notes: str) -> int:
    """Сколько символов остаётся под новый отчёт (с учётом разделителя)."""
    separator = 2 if existing_notes else 0
    return MAX_VERIFICATION_NOTES_LENGTH - len(existing_notes) - separator


def _snapshot(application: PartnerApplication, city_name: Optional[str], type_name: str) -> dict:
    return {
        "full_name": application.full_name,
        "company_name": application.company_name,
        "claimed_type": type_name,
        "activity_type": application.activity_type,
        "city": city_name or application.city_other,
        "website": application.company_website,
        "email": application.email,
        "instagram": application.instagram,
        "facebook": application.facebook,
        "linkedin": application.linkedin,
        "tax_id": application.tax_id,
        "years_in_business": application.years_in_business,
        "team_size": application.team_size,
        "current_brands": application.current_brands,
    }


@router.post("/{application_id}/analyze", response_model=AnalyzeOut)
def analyze_application_endpoint(
    application_id: int,
    payload: AnalyzeIn,
    request: Request,
    session: Session = Depends(get_session),
) -> AnalyzeOut:
    """Запускает AI-анализ анкеты (core/partner_analysis.py) и ДОПИСЫВАЕТ отчёт
    в конец "Заметок проверки" — старые заметки сохраняются. Синхронный запрос,
    может идти несколько минут (веб-поиск) — та же модель, что и у
    POST /api/firm/search. verified_by не трогаем: это отметка живого админа,
    прогнавшего проверку вручную, а не автоматического анализа."""

    _require_admin(request, session)

    application = session.get(PartnerApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Анкета не найдена.")

    city = session.get(City, application.city_id) if application.city_id else None
    firm_type = session.get(FirmType, application.claimed_type_id)
    snapshot = _snapshot(application, city.name if city else None, firm_type.name if firm_type else "")

    # База для дозаписи — то, что админ видит в поле сейчас (может включать
    # ещё не сохранённые правки). last_changed запоминаем, чтобы после долгого
    # вызова понять, не менял ли заметки кто-то ещё за это время.
    notes_at_start = payload.verification_notes
    if notes_at_start is None:
        notes_at_start = application.verification_notes or ""
    notes_at_start = notes_at_start.rstrip()
    last_changed_at_start = application.last_changed
    if payload.last_changed_seen is not None and payload.last_changed_seen != last_changed_at_start:
        raise HTTPException(
            status_code=409,
            detail="Анкету уже изменили в другом месте — обновите страницу и повторите анализ.",
        )

    # Места под отчёт проверяем ДО платного вызова — иначе админ заплатил бы за
    # анализ, чтобы получить 400 и потерять результат.
    if _room_for_report(notes_at_start) < PRECHECK_REPORT_ROOM:
        raise HTTPException(
            status_code=400,
            detail="В заметках проверки не хватает места под отчёт — сократите их и запустите анализ снова.",
        )

    # Параллельный/повторный запуск для той же анкеты (двойной клик, второй
    # админ, повторное открытие карточки) — отказ, а не второй платный анализ.
    with _analysis_lock:
        if application_id in _analysis_in_progress:
            raise HTTPException(status_code=409, detail="Анализ этой анкеты уже выполняется.")
        _analysis_in_progress.add(application_id)

    try:
        # Отпускаем транзакцию/соединение на время долгого внешнего вызова. На
        # SQLite-фолбэке (StaticPool) соединение общее на все сессии, и rollback
        # мог бы откатить чужую незавершённую транзакцию — там не делаем.
        if not IS_SQLITE:
            session.rollback()
        try:
            report = analyze_application(snapshot)
        except PartnerAnalysisError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Непредвиденная ошибка анализа анкеты %s", application_id)
            raise HTTPException(status_code=500, detail="Не удалось выполнить анализ анкеты.") from exc
    finally:
        with _analysis_lock:
            _analysis_in_progress.discard(application_id)

    session.expire_all()
    application = session.get(PartnerApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Анкета не найдена.")

    if application.last_changed != last_changed_at_start:
        # Пока шёл анализ, заметки успели сохранить (другой админ или та же
        # карточка в другой вкладке) — дописываем к актуальному значению из БД,
        # а не затираем чужое сохранённое старой копией из браузера.
        base = (application.verification_notes or "").rstrip()
    else:
        base = notes_at_start

    # Отчёт уже оплачен — пишем его в лог до любых обращений к БД, чтобы он не
    # пропал при сбое сохранения.
    logger.info("Отчёт AI-анализа анкеты %s:\n%s", application_id, report)

    room = _room_for_report(base)
    if room < MIN_REPORT_ROOM:
        # Заметки разрослись за время анализа — отчёт не помещается. Возвращаем
        # его прямо в тексте ошибки, чтобы платный результат не терялся.
        raise HTTPException(
            status_code=400,
            detail="Заметки проверки переполнены — сократите их. Отчёт не сохранён, вот он:\n\n" + report,
        )
    if len(report) > room:
        # Режем середину, но сохраняем последнюю строку отчёта (итог с числом
        # предупреждений) — она важнее хвоста подробностей.
        footer = report.rsplit("\n", 1)[-1]
        marker = "\n…(отчёт обрезан по лимиту длины заметок)\n"
        report = report[: room - len(footer) - len(marker)].rstrip() + marker + footer
    combined = base + ("\n\n" if base else "") + report

    application.verification_notes = combined
    application.last_changed = datetime.utcnow()
    session.add(application)
    session.commit()
    session.refresh(application)

    return AnalyzeOut(verification_notes=application.verification_notes, last_changed=application.last_changed)

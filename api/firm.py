"""
JSON API для работы с фирмами: поиск (кнопка ПОИСК на /crm/firm_finder — js/firmfinder.js)
и ручное создание/редактирование (карточка фирмы на /crm/firms — js/firms.js).
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access, user_has_role
from core.firm_price_download import FirmPriceDownloadError, download_firm_price
from core.firm_search import FirmSearchError, search_firms
from db.database import get_session
from models.city import City
from models.firm import Firm
from models.firm_comment import FirmComment
from models.firm_goods import FirmGoods
from models.firm_price import FirmPrice
from models.firm_price_body import FirmPriceBody
from models.firm_type import FirmType
from models.unit import Unit
from models.users import User


logger = logging.getLogger("infosys.api.firm")

router = APIRouter(prefix="/api/firm", tags=["Firms"])


def _require_authenticated(request: Request, session: Session) -> User:
    state, current_user = resolve_authenticated_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Нужно войти в систему.")
    return current_user


def _get_city_or_404(session: Session, city_id: int) -> City:
    city = session.get(City, city_id)
    if city is None:
        raise HTTPException(status_code=404, detail="Город не найден.")
    return city


def _get_type_or_404(session: Session, type_id: int) -> FirmType:
    firm_type = session.get(FirmType, type_id)
    if firm_type is None:
        raise HTTPException(status_code=404, detail="Тип фирмы не найден.")
    return firm_type


def _get_firm_or_404(session: Session, firm_id: int) -> Firm:
    firm = session.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Фирма не найдена.")
    return firm


def _ensure_can_edit_firm(session: Session, firm: Firm, current_user: User) -> None:
    """Редактировать фирму может только тот, кто её нашёл/добавил, или админ —
    остальные видят карточку read-only (сама карточка видна всем, это не 404)."""
    if firm.user_id == current_user.id or user_has_role(session, current_user.id, "admin"):
        return
    raise HTTPException(
        status_code=403,
        detail="Редактировать фирму может только тот, кто её добавил, или администратор.",
    )


# --- Скачивание прайса (POST /api/firm/{firm_id}/download_price) -----------------

_PRICE_CLEAN_RE = re.compile(r"[^\d,.\-]")
# Артикул часто спрятан в начале названия товара, например "ПБУ-01 Дверь входная
# ..." — короткий код из букв/цифр (лат. или кириллица), возможно с дефисом,
# затем пробел и остальная часть названия. Подстраховка на случай, если модель
# не разделила название и артикул сама, как её просили в системном промпте.
# Требуем хотя бы одну цифру в префиксе — иначе обычные материаловые/брендовые
# сокращения без цифр (например "МДФ Дверь ...", "ПВХ панель ...") ошибочно
# принимались бы за артикул.
_LEADING_ARTICLE_RE = re.compile(r"^(?=[A-ZА-ЯЁ0-9\-]*\d)([A-ZА-ЯЁ0-9]{2,10}(?:-[A-ZА-ЯЁ0-9]{1,6})?)\s+(.+)$")
_SLUG_WS_RE = re.compile(r"[\s_]+")
_SLUG_INVALID_RE = re.compile(r"[^\w\-]+", re.UNICODE)

_UNIT_SYNONYMS = {
    "шт": "шт", "шт.": "шт", "штук": "шт", "штука": "шт", "pcs": "шт", "pc": "шт",
    # "комплект" — типичная для дверных сайтов единица (дверь продаётся в сборе
    # со всеми компонентами); ближайший по смыслу вариант из имеющихся — "шт".
    "комплект": "шт", "компл": "шт", "компл.": "шт", "к-т": "шт",
    "м": "м", "м.": "м", "метр": "м", "п.м": "м", "п.м.": "м", "пог.м": "м",
    "м2": "м2", "м²": "м2", "кв.м": "м2", "кв.м.": "м2", "m2": "м2",
    "мм": "мм", "мм.": "мм", "mm": "мм",
    "л": "л", "л.": "л", "литр": "л",
}


def _parse_price(raw: object) -> Optional[Decimal]:
    """Приводит цену из ответа ИИ (число или строка с валютой/пробелами) к Decimal."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            return None
    elif isinstance(raw, str):
        text = _PRICE_CLEAN_RE.sub("", raw).strip()
        if not text:
            return None
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif text.count(",") == 1:
            # Один разделитель без точки рядом — неоднозначно: "8,730" на
            # реальном сайте оказалось "8730 грн" (тысячи), а "150,50" — это
            # "150.50" (копейки). Валюта почти всегда даёт ровно 2 знака после
            # разделителя для копеек — 3 знака куда чаще тысячи. При остальных
            # длинах (не 2 и не 3) считаем разделителем дробную часть, как раньше.
            digits_after = len(text.split(",", 1)[1])
            if digits_after == 3:
                text = text.replace(",", "")
            else:
                text = text.replace(",", ".")
        elif "," in text:
            text = text.replace(",", "")
        try:
            value = Decimal(text)
        except InvalidOperation:
            return None
    else:
        return None

    if value <= 0:
        return None
    return value.quantize(Decimal("0.01"))


def _split_leading_article(name: str) -> tuple[Optional[str], str]:
    match = _LEADING_ARTICLE_RE.match(name.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, name.strip()


def _slugify_article(name: str) -> str:
    normalized = _SLUG_WS_RE.sub("-", name.strip().lower())
    normalized = _SLUG_INVALID_RE.sub("", normalized)
    normalized = normalized.strip("-")
    return normalized[:100] or "tovar"


def _dedupe_article(article: str, taken_lower: set[str]) -> str:
    """article уникален только в рамках фирмы (firm_id, article) — если сгенерированный
    /присланный код уже занят другим товаром этой фирмы, добавляем числовой суффикс.
    Сравнение регистронезависимое (taken_lower уже в нижнем регистре) — иначе
    "ПБУ-01" и "пбу-01" в разных запусках считались бы разными кодами, хотя
    физически это один и тот же товар."""
    if article.lower() not in taken_lower:
        return article
    suffix = 2
    while f"{article}-{suffix}".lower() in taken_lower:
        suffix += 1
    return f"{article}-{suffix}"


def _resolve_unit(session: Session, raw_unit: Optional[str]) -> Optional[Unit]:
    if not raw_unit:
        return None
    canonical = _UNIT_SYNONYMS.get(raw_unit.strip().lower())
    if canonical is None:
        return None
    return session.exec(select(Unit).where(Unit.name == canonical)).first()


def _prepare_price_items(raw_items: list[dict]) -> list[dict]:
    """Нормализует ответ download_firm_price(): парсит цену, при отсутствии
    явного article в ответе пробует извлечь его из начала названия.

    Дедуп в рамках одного ответа — по (название, артикул), а не только по
    названию: разные варианты товара под одним и тем же базовым названием
    (например, два цвета одной двери с разными артикулами) — это разные
    товары, только артикул их и отличает, дублем считаем только полное
    совпадение и названия, и артикула (или отсутствие артикула у обоих)."""
    prepared = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        price = _parse_price(item.get("price"))
        if price is None:
            continue

        name = item["name"]
        article = item.get("article")
        if not article:
            article, name = _split_leading_article(name)

        name_key = name.strip().lower()
        if not name_key:
            continue
        article_key = article.strip().lower() if article else ""
        dedup_key = (name_key, article_key)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        prepared.append({"name": name, "article": article, "unit": item.get("unit"), "price": price})
    return prepared


class FirmPriceDownloadOut(BaseModel):
    price_id: int
    created: date
    item_count: int


class FirmCommentIn(BaseModel):
    comment: str = Field(..., min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Примечание не может быть пустым.")
        return stripped


class FirmCommentOut(BaseModel):
    id: int
    added: datetime
    author_fullname: str
    comment: str


class FirmSearchIn(BaseModel):
    city_id: int
    type_id: int


class FirmMutateMixin(BaseModel):
    city_id: int
    type_id: int
    name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=50)
    website: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=500)
    source: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)
    rating: int = Field(default=5, ge=0, le=10)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Название не может быть пустым.")
        return stripped

    @field_validator("phone", "website", "address", "source", "notes")
    @classmethod
    def strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class FirmCreateIn(FirmMutateMixin):
    """Ручное добавление фирмы через кнопку "+" на /crm/firms."""


class FirmEditIn(FirmMutateMixin):
    """Редактирование фирмы через карточку — полная замена изменяемых полей."""


class FirmOut(BaseModel):
    id: int
    city_id: int
    type_id: int
    name: str
    phone: Optional[str]
    website: Optional[str]
    address: Optional[str]
    source: Optional[str]
    notes: Optional[str]
    rating: int


def _to_firm_out(firm: Firm) -> FirmOut:
    return FirmOut(
        id=firm.id,
        city_id=firm.city_id,
        type_id=firm.type_id,
        name=firm.name,
        phone=firm.phone,
        website=firm.website,
        address=firm.address,
        source=firm.source,
        notes=firm.notes,
        rating=firm.rating,
    )


@router.post("/search", response_model=list[FirmOut])
def search(
    payload: FirmSearchIn, request: Request, session: Session = Depends(get_session)
) -> list[FirmOut]:
    current_user = _require_authenticated(request, session)
    city = _get_city_or_404(session, payload.city_id)
    firm_type = _get_type_or_404(session, payload.type_id)

    try:
        found = search_firms(city.name, firm_type.name)
    except FirmSearchError as exc:
        logger.warning("Поиск фирм не удался: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    existing_names = {
        name.strip().lower()
        for name in session.exec(
            select(Firm.name).where(Firm.city_id == city.id, Firm.type_id == firm_type.id)
        ).all()
    }

    created: list[Firm] = []
    for item in found:
        key = item["name"].strip().lower()
        if key in existing_names:
            continue
        existing_names.add(key)
        firm = Firm(
            city_id=city.id,
            type_id=firm_type.id,
            user_id=current_user.id,
            name=item["name"],
            phone=item["phone"],
            website=item["website"],
            address=item["address"],
            source=item["source"],
            notes=item["notes"],
        )
        session.add(firm)
        created.append(firm)

    session.commit()
    for firm in created:
        session.refresh(firm)

    return [_to_firm_out(firm) for firm in created]


@router.post("", response_model=FirmOut, status_code=201)
def create_firm(
    payload: FirmCreateIn, request: Request, session: Session = Depends(get_session)
) -> FirmOut:
    current_user = _require_authenticated(request, session)
    _get_city_or_404(session, payload.city_id)
    _get_type_or_404(session, payload.type_id)

    firm = Firm(
        city_id=payload.city_id,
        type_id=payload.type_id,
        user_id=current_user.id,
        name=payload.name,
        phone=payload.phone,
        website=payload.website,
        address=payload.address,
        source=payload.source,
        notes=payload.notes,
        rating=payload.rating,
    )
    session.add(firm)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Не удалось добавить фирму — проверьте город и тип.")
    session.refresh(firm)

    return _to_firm_out(firm)


@router.patch("/{firm_id}", response_model=FirmOut)
def edit_firm(
    firm_id: int, payload: FirmEditIn, request: Request, session: Session = Depends(get_session)
) -> FirmOut:
    current_user = _require_authenticated(request, session)
    firm = _get_firm_or_404(session, firm_id)
    _ensure_can_edit_firm(session, firm, current_user)
    _get_city_or_404(session, payload.city_id)
    _get_type_or_404(session, payload.type_id)

    firm.city_id = payload.city_id
    firm.type_id = payload.type_id
    firm.name = payload.name
    firm.phone = payload.phone
    firm.website = payload.website
    firm.address = payload.address
    firm.source = payload.source
    firm.notes = payload.notes
    firm.rating = payload.rating
    session.add(firm)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Не удалось сохранить фирму — проверьте город и тип.")
    session.refresh(firm)

    return _to_firm_out(firm)


@router.post("/{firm_id}/download_price", response_model=FirmPriceDownloadOut, status_code=201)
async def download_price(
    firm_id: int, request: Request, session: Session = Depends(get_session)
) -> FirmPriceDownloadOut:
    """Кнопка "Скачать прайс" на /crm/firms/{id}/prices — сами скачиваем сайт фирмы
    (см. core/firm_price_download.py) и извлекаем актуальные цены на двери
    (окна/балконы исключаются), создавая один новый firm_price (дата+примечание) и
    связанные firm_goods/firm_price_body. Роут асинхронный (не sync def, как
    остальные в этом файле) — download_firm_price теперь сама async: скачивание
    страниц идёт через httpx.AsyncClient, а не через блокирующий синхронный вызов,
    который держал бы воркер-поток FastAPI занятым на всё время загрузки."""
    _require_authenticated(request, session)
    firm = _get_firm_or_404(session, firm_id)

    website = (firm.website or "").strip()
    if not website:
        raise HTTPException(
            status_code=400, detail="У фирмы не указан сайт — скачивание прайса недоступно."
        )
    if not website.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Некорректный адрес сайта фирмы.")

    try:
        raw_items = await download_firm_price(firm.name, website)
    except FirmPriceDownloadError as exc:
        logger.warning("Скачивание прайса не удалось (firm_id=%s): %s", firm_id, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    items = _prepare_price_items(raw_items)
    if not items:
        raise HTTPException(status_code=422, detail="На сайте не найдено актуальных цен на двери.")

    default_unit = session.exec(select(Unit).where(Unit.name == "шт")).first()
    if default_unit is None:
        raise HTTPException(
            status_code=500,
            detail='Не найдена единица измерения по умолчанию ("шт") — обратитесь к администратору.',
        )

    # Переиспользование по названию — сквозная политика между разными скачиваниями
    # (одна и та же db-запись firm_goods, если название уже встречалось раньше).
    existing_goods = {
        g.name.strip().lower(): g
        for g in session.exec(select(FirmGoods).where(FirmGoods.firm_id == firm.id)).all()
    }
    taken_articles_lower = {g.article.lower() for g in existing_goods.values()}

    price = FirmPrice(
        firm_id=firm.id,
        created=datetime.utcnow().date(),
        rem=f"Загружено автоматически с сайта {website}",
    )
    session.add(price)

    # Внутри ОДНОГО скачивания название может повторяться с разными артикулами
    # (например два цвета одной и той же двери) — это разные товары, и второе
    # вхождение того же названия не должно молча склеиваться с первым, иначе
    # второй insert в firm_price_body упадёт на уникальности (price_id, good_id).
    # names_with_other_article отслеживает такие названия, чтобы для них ВСЕГДА
    # заводить отдельный firm_goods, даже если первое вхождение этого названия
    # уже переиспользовало существующую db-запись.
    article_by_name_in_batch: dict[str, str] = {}
    for item in items:
        name_key = item["name"].strip().lower()
        article_key = (item["article"] or "").strip().lower()
        prior = article_by_name_in_batch.get(name_key)
        if prior is not None and prior != article_key:
            article_by_name_in_batch[name_key] = "__MULTIPLE__"
        else:
            article_by_name_in_batch[name_key] = article_key

    plan: list[tuple[FirmGoods, Decimal]] = []
    for item in items:
        name_key = item["name"].strip().lower()
        name_has_multiple_articles = article_by_name_in_batch.get(name_key) == "__MULTIPLE__"

        good = None if name_has_multiple_articles else existing_goods.get(name_key)
        if good is None:
            article = item["article"] or _slugify_article(item["name"])
            article = _dedupe_article(article, taken_articles_lower)
            taken_articles_lower.add(article.lower())

            unit = _resolve_unit(session, item["unit"]) or default_unit
            good = FirmGoods(firm_id=firm.id, article=article, name=item["name"], unit_id=unit.id)
            session.add(good)
            if not name_has_multiple_articles:
                existing_goods[name_key] = good
        plan.append((good, item["price"]))

    try:
        session.flush()  # назначает id для price и для всех новых good — внутри try,
        # чтобы столкновение уникальности (гонка параллельных скачиваний одной и
        # той же фирмы) тоже откатывалось аккуратно, а не 500-кой без rollback.

        body_rows = [
            FirmPriceBody(price_id=price.id, good_id=good.id, price=item_price) for good, item_price in plan
        ]
        session.add_all(body_rows)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Не удалось сохранить скачанный прайс.")
    session.refresh(price)

    return FirmPriceDownloadOut(price_id=price.id, created=price.created, item_count=len(body_rows))


# --- Примечания к фирме (GET-страница /crm/firms/{id}/comments, см. views/crm/firm_comments.py) ---


@router.post("/{firm_id}/comments", response_model=FirmCommentOut, status_code=201)
def add_comment(
    firm_id: int, payload: FirmCommentIn, request: Request, session: Session = Depends(get_session)
) -> FirmCommentOut:
    """Добавление примечания — любым авторизованным пользователем (не только
    владельцем/админом фирмы, как _ensure_can_edit_firm для самой карточки —
    примечания это отдельный, более открытый журнал). Записи неизменяемы —
    ни PATCH, ни DELETE для firm_comment не предусмотрены."""
    current_user = _require_authenticated(request, session)
    _get_firm_or_404(session, firm_id)

    comment = FirmComment(firm_id=firm_id, user_id=current_user.id, comment=payload.comment)
    session.add(comment)
    session.commit()
    session.refresh(comment)

    return FirmCommentOut(
        id=comment.id, added=comment.added, author_fullname=current_user.fullname, comment=comment.comment
    )

"""
Чистая (без обращений к БД) логика поиска аномалий в списке заказов (Zakaz)
для отчёта по кнопке "Анализ" на /crm/zakaz (см. api/zakaz.py, который строит
список ZakazRow из отфильтрованных строк и вызывает analyze_zakaz()).

Анализируется всегда только то, что уже прошло через фильтр страницы — вызов
этого модуля не знает о фильтрах вообще, он просто обрабатывает переданный
список строк.
"""

import re
from dataclasses import dataclass, field
from datetime import date


# Ключевые слова, по которым адрес доставки считается точкой самовывоза/службы
# доставки, а не физическим адресом получателя (рус/укр/англ варианты
# написания). Список сознательно не претендует на полноту — расширять по мере
# появления новых случаев.
_PICKUP_KEYWORDS = (
    "нова пошта",
    "новая почта",
    "укрпошта",
    "укрпочта",
    "деливери",
    "delivery",
    "meest",
    "міст експрес",
    "самовивіз",
    "самовывоз",
    "відділення",
    "отделение",
    "пункт видачі",
    "пункт выдачи",
    "поштомат",
    "почтомат",
)

# Наличие цифры в адресе — грубый, но рабочий признак того, что в адресе
# указан номер дома/строения. Его отсутствие — сигнал неполного адреса.
# Почтовый индекс (5 цифр подряд, отдельным "словом") из этой проверки
# исключается: "01001, Київська, Київ, Київ" содержит цифру, но это индекс,
# а не номер дома/улицы — без вычитания индекса такой адрес ошибочно
# считался бы полным (баг, найденный пользователем вручную на реальных данных).
_HAS_DIGIT_RE = re.compile(r"\d")
_POSTAL_CODE_RE = re.compile(r"\b\d{5}\b")

_PLACEHOLDER_VALUES = {"-", "—", "–", "нет", "немає", "невідомо", "неизвестно", "н/д", "n/a"}


def _normalize(addr: str) -> str:
    return " ".join((addr or "").strip().casefold().split())


def _is_incomplete(addr: str) -> bool:
    normalized = _normalize(addr)
    if not normalized or normalized in _PLACEHOLDER_VALUES or len(normalized) < 5:
        return True
    without_postal_code = _POSTAL_CODE_RE.sub("", normalized)
    return not _HAS_DIGIT_RE.search(without_postal_code)


def _is_pickup(addr: str) -> bool:
    normalized = _normalize(addr)
    return any(keyword in normalized for keyword in _PICKUP_KEYWORDS)


@dataclass
class ZakazRow:
    """Одна строка заказа, уже отфильтрованная по критериям страницы."""

    num: str
    ord_date: date
    delivery_addr: str
    city_name: str
    anketa_id: int
    firm_name: str


@dataclass
class AnomalyGroup:
    title: str
    subtitle: str = ""
    orders: list = field(default_factory=list)


@dataclass
class AnomalyCategory:
    key: str
    label: str
    description: str
    groups: list = field(default_factory=list)
    # "firm" — группа = одна фирма (её имя уже вынесено в заголовок группы,
    # повторять в каждой строке заказа незачем — see api/zakaz.py/js/zakaz.js,
    # колонка "Фирма" в таблице заказов для таких категорий не рисуется).
    # "address" — группа = один адрес, разные фирмы (единственная категория,
    # где название фирмы — и есть суть аномалии, поэтому колонка нужна).
    group_by: str = "firm"

    @property
    def order_count(self) -> int:
        return sum(len(g.orders) for g in self.groups)


def _order_dict(row: ZakazRow) -> dict:
    return {
        "num": row.num,
        "ord_date": row.ord_date.isoformat(),
        "delivery_addr": row.delivery_addr,
        "city_name": row.city_name,
        "firm_name": row.firm_name,
    }


def analyze_zakaz(rows: list[ZakazRow]) -> list[AnomalyCategory]:
    """Возвращает список категорий аномалий (только те, где что-то нашлось,
    в фиксированном порядке — от самой "дешёвой"/точной проверки к самой
    эвристической)."""

    categories: list[AnomalyCategory] = []

    # 1. Адрес не указан или неполный (пусто, плейсхолдер, или нет ни одной
    # цифры — то есть, скорее всего, нет номера дома).
    by_firm_incomplete: dict[int, AnomalyGroup] = {}
    for row in rows:
        if _is_incomplete(row.delivery_addr):
            group = by_firm_incomplete.setdefault(
                row.anketa_id, AnomalyGroup(title=row.firm_name)
            )
            group.orders.append(_order_dict(row))
    if by_firm_incomplete:
        categories.append(
            AnomalyCategory(
                key="incomplete_address",
                label="Адрес не указан или неполный",
                description="Адрес доставки пуст, содержит заглушку ('-', 'нет' и т.п.) "
                "или не содержит ни одной цифры (похоже, что нет номера дома).",
                groups=sorted(by_firm_incomplete.values(), key=lambda g: g.title),
            )
        )

    # 2. Адрес доставки — точка самовывоза/служба доставки (Новая почта,
    # Деливери и т.д.), а не физический адрес получателя.
    by_firm_pickup: dict[int, AnomalyGroup] = {}
    for row in rows:
        if _is_pickup(row.delivery_addr):
            group = by_firm_pickup.setdefault(row.anketa_id, AnomalyGroup(title=row.firm_name))
            group.orders.append(_order_dict(row))
    if by_firm_pickup:
        categories.append(
            AnomalyCategory(
                key="pickup_service",
                label="Адрес — пункт самовывоза/служба доставки",
                description="В адресе доставки упоминается служба доставки или пункт "
                "самовывоза (Новая почта, Деливери и т.п.), а не адрес получателя.",
                groups=sorted(by_firm_pickup.values(), key=lambda g: g.title),
            )
        )

    # 3. Одна фирма — разные адреса доставки (среди непустых, неплейсхолдерных
    # адресов; пустые адреса уже учтены в категории 1 и не должны размывать
    # эту проверку). Пункты самовывоза/служб доставки исключены той же логикой,
    # что и в категории 4 ниже: заказчику совершенно нормально получать заказы
    # на разные отделения Новой почты в разных городах — это не аномалия
    # адреса, это обычная практика. Неполные адреса (категория 1) тоже
    # исключены: "79000, Львівська, Львів, ЛЬВІВ" (индекс+область+город без
    # улицы) — не второй "другой" адрес фирмы, а просто ещё один заказ без
    # указанной улицы, и не должен считаться отдельным реальным адресом
    # (реальный случай, найденный пользователем на живых данных).
    addrs_by_firm: dict[int, dict] = {}  # anketa_id -> {normalized_addr: [rows]}
    firm_name_by_id: dict[int, str] = {}
    for row in rows:
        normalized = _normalize(row.delivery_addr)
        firm_name_by_id[row.anketa_id] = row.firm_name
        if (
            not normalized
            or normalized in _PLACEHOLDER_VALUES
            or _is_pickup(row.delivery_addr)
            or _is_incomplete(row.delivery_addr)
        ):
            continue
        addrs_by_firm.setdefault(row.anketa_id, {}).setdefault(normalized, []).append(row)

    firm_multi_groups = []
    for anketa_id, addr_map in addrs_by_firm.items():
        if len(addr_map) > 1:
            group = AnomalyGroup(
                title=firm_name_by_id[anketa_id],
                subtitle=f"{len(addr_map)} разных адресов",
            )
            for addr_rows in addr_map.values():
                for row in addr_rows:
                    group.orders.append(_order_dict(row))
            group.orders.sort(key=lambda o: (o["delivery_addr"], o["num"]))
            firm_multi_groups.append(group)
    if firm_multi_groups:
        categories.append(
            AnomalyCategory(
                key="firm_multiple_addresses",
                label="Одна фирма — разные адреса доставки",
                description="У одной фирмы заказы уходят на несколько разных адресов доставки "
                "(точки самовывоза/службы доставки и неполные адреса без улицы в счёт "
                "не идут — совпадение/различие там ничего не значит).",
                groups=sorted(firm_multi_groups, key=lambda g: g.title),
            )
        )

    # 4. Один адрес доставки — разные фирмы. Пункты самовывоза/служб доставки
    # исключены сознательно: разным фирмам совершенно нормально получать на
    # одно и то же отделение Новой почты, это не аномалия. Неполные адреса
    # (категория 1) тоже исключены — иначе, например, "01001, Київська, Київ,
    # Київ" (индекс+область+город без улицы) у десятка разных фирм из одного
    # города совпадает буквально, и это ложно выглядит как "один адрес —
    # разные фирмы", хотя на самом деле это просто у всех не указана улица
    # (реальный случай, найденный пользователем на живых данных).
    addr_groups: dict[str, dict] = {}  # normalized_addr -> {anketa_id: [rows]}
    raw_addr_by_norm: dict[str, str] = {}
    for row in rows:
        normalized = _normalize(row.delivery_addr)
        if (
            not normalized
            or normalized in _PLACEHOLDER_VALUES
            or _is_pickup(row.delivery_addr)
            or _is_incomplete(row.delivery_addr)
        ):
            continue
        raw_addr_by_norm.setdefault(normalized, row.delivery_addr)
        addr_groups.setdefault(normalized, {}).setdefault(row.anketa_id, []).append(row)

    addr_multi_groups = []
    for normalized, firm_map in addr_groups.items():
        if len(firm_map) > 1:
            group = AnomalyGroup(
                title=raw_addr_by_norm[normalized],
                subtitle=f"{len(firm_map)} разных фирм",
            )
            for firm_rows in firm_map.values():
                for row in firm_rows:
                    group.orders.append(_order_dict(row))
            group.orders.sort(key=lambda o: (o["firm_name"], o["num"]))
            addr_multi_groups.append(group)
    if addr_multi_groups:
        categories.append(
            AnomalyCategory(
                key="address_multiple_firms",
                label="Один адрес доставки — разные фирмы",
                description="На один и тот же адрес доставки оформлены заказы от разных фирм "
                "(точки самовывоза/службы доставки и неполные адреса без улицы в этот список "
                "не попадают — совпадение там ничего не значит).",
                groups=sorted(addr_multi_groups, key=lambda g: g.title),
                group_by="address",
            )
        )

    # 5. Бонус: похожие на дубликаты заказы — одна фирма, один и тот же адрес,
    # одна и та же дата, несколько разных номеров заказа. Может быть и
    # легитимным (крупный заказ разбит на несколько документов), но стоит
    # взглянуть глазами. Неполные адреса исключены той же логикой, что и в
    # категории 4 — два заказа одной фирмы в один день с одинаково пустой
    # "улицей" не значит, что это один и тот же реальный адрес.
    dup_key_map: dict[tuple, list] = {}
    for row in rows:
        normalized = _normalize(row.delivery_addr)
        if not normalized or normalized in _PLACEHOLDER_VALUES or _is_incomplete(row.delivery_addr):
            continue
        dup_key_map.setdefault((row.anketa_id, normalized, row.ord_date), []).append(row)

    dup_groups = []
    for (anketa_id, _normalized, ord_date_key), dup_rows in dup_key_map.items():
        if len(dup_rows) > 1:
            group = AnomalyGroup(
                title=firm_name_by_id[anketa_id],
                subtitle=f"{ord_date_key.isoformat()}, {len(dup_rows)} заказов на один адрес в один день",
                orders=[_order_dict(row) for row in dup_rows],
            )
            dup_groups.append(group)
    if dup_groups:
        categories.append(
            AnomalyCategory(
                key="same_day_duplicates",
                label="Возможные дубли: одна фирма, один адрес, одна дата",
                description="В один день на один и тот же адрес от одной фирмы оформлено "
                "несколько заказов — возможно, случайный дубль (а возможно, легитимное "
                "разбиение крупного заказа на несколько документов).",
                groups=sorted(dup_groups, key=lambda g: (g.title, g.subtitle)),
            )
        )

    return categories


def serialize_categories(categories: list[AnomalyCategory]) -> list[dict]:
    """JSON-готовое представление analyze_zakaz()'s результата — api/zakaz.py
    отдаёт его как есть, js/zakaz.js рендерит без дополнительной обработки."""

    return [
        {
            "key": category.key,
            "label": category.label,
            "description": category.description,
            "order_count": category.order_count,
            "group_by": category.group_by,
            "groups": [
                {
                    "title": group.title,
                    "subtitle": group.subtitle,
                    "orders": group.orders,
                }
                for group in category.groups
            ],
        }
        for category in categories
    ]

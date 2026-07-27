import math
from typing import Optional

from fastapi import Depends, Request
from sqlmodel import Session, func, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.city import City
from models.firm import Firm
from models.firm_type import FirmType
from models.task import Task
from models.task_status import TaskStatus
from views.base import render_page


# r + stroke_width/2 = 50 + 12 = 62, comfortably inside the 140x140 viewBox's
# 70-unit half-dimension (used in templates/crm/crm.html) — leaves margin so the
# stroke isn't clipped by the SVG's default overflow:hidden at the viewBox edge.
DONUT_RADIUS = 50
DONUT_STROKE_WIDTH = 24
DONUT_CIRCUMFERENCE = 2 * math.pi * DONUT_RADIUS
DONUT_GAP = 3  # px — surface gap between slices, per the dataviz skill's spacer rule

# Invisible, much fatter stroke drawn under the visible ring for each clickable
# slice — the visible ring itself is a thin arc, way too small/precise a target
# to click reliably ("pinpoint hover target" anti-pattern); this widens the real
# hit area into a full pie-wedge from the center out to just inside the viewBox
# edge (34 - 34 = 0 .. 34 + 34 = 68 < the 70-unit half-viewBox), without the 3px
# inter-slice gap (a slightly generous target is what you want, not a precise one).
DONUT_HIT_RADIUS = 34
DONUT_HIT_STROKE_WIDTH = 68

# Категориальная палитра dataviz-скилла (8 слотов, фиксированный порядок — CVD-safe).
# Цвет закреплён за сущностью (городом/типом), а не за её местом в текущей выборке,
# чтобы фильтрация нулевых категорий не перекрашивала остальные (anti-pattern:
# "recolor-on-filter").
CATEGORICAL_PALETTE = [
    "#2a78d6", "#008300", "#e87ba4", "#eda100",
    "#1baf7a", "#eb6834", "#4a3aa7", "#e34948",
]
OTHER_COLOR = "#898781"  # приглушённые чернила — для категорий сверх 8 слотов ("Other")


def _status_breakdown(statuses: list[TaskStatus], session: Session, owner_column, user_id: int) -> list[dict]:
    """Считает число задач пользователя (по колонке author_id или assignee_id)
    в разбивке по статусам — включая статусы с нулём задач, для полной картины."""
    rows = session.exec(
        select(Task.status_id, func.count(Task.id))
        .where(owner_column == user_id)
        .group_by(Task.status_id)
    ).all()
    counts_by_status = dict(rows)

    max_count = max(counts_by_status.values(), default=0) or 1

    return [
        {
            "label": status.name,
            "count": counts_by_status.get(status.id, 0),
            "pct": round(counts_by_status.get(status.id, 0) / max_count * 100, 1),
        }
        for status in statuses
    ]


def _assign_slots(ordered_ids: list[int]) -> dict[int, str]:
    """Закрепляет цвет за каждой сущностью по фиксированному порядку (id по возрастанию —
    порядок создания), только для первых 8 категориальных слотов. Сущности сверх
    восьми сюда намеренно не попадают — _build_rows() схлопывает их всех в одну
    строку "Другое" (общий серый, а не сгенерированный 9-й оттенок; anti-pattern:
    "cycling hues past 8"), что было бы невозможно отличить, если бы они тоже
    попали в этот словарь под OTHER_COLOR."""
    return {
        entity_id: CATEGORICAL_PALETTE[index]
        for index, entity_id in enumerate(ordered_ids)
        if index < len(CATEGORICAL_PALETTE)
    }


def _build_rows(
    entities: list[tuple[int, str]], colors: dict[int, str], counts: dict[int, int]
) -> list[tuple[Optional[int], str, int]]:
    """Строит строки для _donut_breakdown из полного упорядоченного списка сущностей:
    пропускает нулевые категории, а всё, что вышло за пределы 8 цветовых слотов
    (нет в colors), схлопывает в одну строку "Другое" с суммарным count — иначе
    несколько разных категорий делили бы один и тот же серый цвет и на кольце
    выглядели бы как единый (при этом неверный по размеру) сектор."""
    rows: list[tuple[Optional[int], str, int]] = []
    other_count = 0
    for entity_id, name in entities:
        count = counts.get(entity_id, 0)
        if count <= 0:
            continue
        if entity_id in colors:
            rows.append((entity_id, name, count))
        else:
            other_count += count
    if other_count > 0:
        rows.append((None, "Другое", other_count))
    return rows


def _donut_breakdown(rows: list[tuple[Optional[int], str, int]], colors: dict[int, str]) -> list[dict]:
    """rows — уже отфильтрованные вызывающим кодом (только count > 0) тройки
    (entity_id, label, count); entity_id может быть None для схлопнутой строки
    "Другое" из _build_rows(). Считает dasharray/поворот для SVG-кольца, самый
    крупный сегмент — первым."""
    total = sum(count for _, _, count in rows)
    if total == 0:
        return []

    rows_sorted = sorted(rows, key=lambda r: r[2], reverse=True)
    result = []
    cumulative_deg = 0.0
    for entity_id, label, count in rows_sorted:
        pct = count / total * 100
        arc_length = max(pct / 100 * DONUT_CIRCUMFERENCE - DONUT_GAP, 0)
        hit_arc_length = pct / 100 * DONUT_CIRCUMFERENCE  # no gap subtracted — a slightly generous hit target
        result.append(
            {
                "id": entity_id,  # None for the merged "Другое" row — nothing single to filter by
                "label": label,
                "count": count,
                "pct": round(pct, 1),
                "color": colors.get(entity_id, OTHER_COLOR),
                "dash_array": f"{arc_length:.2f} {DONUT_CIRCUMFERENCE - arc_length:.2f}",
                "hit_dash_array": f"{hit_arc_length:.2f} {DONUT_CIRCUMFERENCE - hit_arc_length:.2f}",
                "rotate_deg": round(cumulative_deg, 2),
            }
        )
        cumulative_deg += pct / 100 * 360
    return result


def _firm_city_breakdown(session: Session) -> list[dict]:
    """Количество фирм по городам — глобально, по всей базе (не по текущему
    пользователю), в отличие от графиков по задачам выше: таблица firm общая
    для всех, без фильтрации по пользователю нигде в проекте."""
    cities = session.exec(select(City).order_by(City.id)).all()
    colors = _assign_slots([city.id for city in cities])

    counts = dict(session.exec(select(Firm.city_id, func.count(Firm.id)).group_by(Firm.city_id)).all())
    rows = _build_rows([(city.id, city.name) for city in cities], colors, counts)

    return _donut_breakdown(rows, colors)


def _firm_type_breakdown(session: Session) -> list[dict]:
    """Количество фирм по типам — глобально, по всей базе (см. _firm_city_breakdown)."""
    firm_types = session.exec(select(FirmType).order_by(FirmType.id)).all()
    colors = _assign_slots([firm_type.id for firm_type in firm_types])

    counts = dict(session.exec(select(Firm.type_id, func.count(Firm.id)).group_by(Firm.type_id)).all())
    rows = _build_rows([(ft.id, ft.name) for ft in firm_types], colors, counts)

    return _donut_breakdown(rows, colors)


def crm_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "crm", {"next": "/crm"})

    statuses = session.exec(select(TaskStatus).order_by(TaskStatus.id)).all()
    authored_chart = _status_breakdown(statuses, session, Task.author_id, current_user.id)
    assigned_chart = _status_breakdown(statuses, session, Task.assignee_id, current_user.id)

    firm_city_chart = _firm_city_breakdown(session)
    firm_type_chart = _firm_type_breakdown(session)

    return render_page(
        request,
        "crm/crm.html",
        "CRM",
        "crm",
        {
            "authored_chart": authored_chart,
            "assigned_chart": assigned_chart,
            "firm_city_chart": firm_city_chart,
            "firm_type_chart": firm_type_chart,
            "donut_radius": DONUT_RADIUS,
            "donut_stroke_width": DONUT_STROKE_WIDTH,
            "donut_hit_radius": DONUT_HIT_RADIUS,
            "donut_hit_stroke_width": DONUT_HIT_STROKE_WIDTH,
        },
    )

from typing import Optional

from fastapi import Depends, Request
from sqlalchemy import func
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.channel_type import ChannelType
from models.city import City
from models.firm import Firm
from models.firm_channel import FirmChannel
from models.firm_event import FirmEvent
from models.users import User
from views.base import render_page


PAGE_SIZE = 10


def _parse_positive_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 1 else None


def events_page(
    request: Request,
    page: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Глобальный список событий по ВСЕМ фирмам (аналог /crm/firms/{id}/events,
    только без привязки к одной фирме) — см. views/crm/firm_events.py для
    страницы, специфичной для конкретной фирмы. Полноценно доступны просмотр,
    добавление и корректировка любому авторизованному пользователю (по явному
    запросу — "чтобы менеджеру было проще"), без ограничения владельцем/админом
    фирмы, той же логикой, что и на странице событий одной фирмы."""
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "crm", {"next": "/crm/events"})

    page_num = _parse_positive_int(page) or 1

    total = session.exec(select(func.count()).select_from(FirmEvent)).one()
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page_num = min(max(page_num, 1), total_pages)

    # Все каналы связи всех фирм — нужны и для колонки "Канал связи" каждой
    # строки (select для смены канала в пределах ТОЙ ЖЕ фирмы, см. PATCH
    # /api/firm/{firm_id}/events/{event_id}), и для каскадного выбора при
    # добавлении нового события (сначала фирма, потом её канал).
    channel_rows = session.exec(
        select(FirmChannel, ChannelType).join(ChannelType, ChannelType.id == FirmChannel.channel_id)
        .order_by(ChannelType.name, FirmChannel.address)
    ).all()
    channels_by_firm: dict[int, list[dict]] = {}
    for channel, channel_type in channel_rows:
        channels_by_firm.setdefault(channel.firm_id, []).append(
            {"id": channel.id, "label": f"{channel_type.name}: {channel.address}"}
        )

    rows = session.exec(
        select(FirmEvent, FirmChannel, Firm, City, User)
        .join(FirmChannel, FirmChannel.id == FirmEvent.channel_id)
        .join(Firm, Firm.id == FirmChannel.firm_id)
        .join(City, City.id == Firm.city_id)
        .join(User, User.id == FirmEvent.user_id)
        .order_by(FirmEvent.created.desc(), FirmEvent.id.desc())
        .offset((page_num - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    events = [
        {
            "event": event,
            "firm": firm,
            "city": city,
            "author": author,
            "firm_channels": channels_by_firm.get(firm.id, []),
        }
        for event, channel, firm, city, author in rows
    ]

    # Список всех фирм (с городом) + их каналов — для <select> "фирма"/"канал" в
    # форме добавления нового события. Построено как plain dict, не ORM-объекты
    # — Jinja |tojson не умеет сериализовать SQLModel-объекты напрямую (тот же
    # приём, что и window.ALL_CHANNEL_TYPES/window.OPEN_USER_ID в других местах).
    firm_rows = session.exec(select(Firm, City).join(City, City.id == Firm.city_id).order_by(Firm.name)).all()
    firms_with_channels = [
        {"id": firm.id, "label": f"{firm.name} ({city.name})", "channels": channels_by_firm.get(firm.id, [])}
        for firm, city in firm_rows
    ]

    return render_page(
        request,
        "crm/events.html",
        "События",
        "crm",
        {
            "events": events,
            "firms_with_channels": firms_with_channels,
            "page": page_num,
            "total_pages": total_pages,
            "total": total,
        },
    )

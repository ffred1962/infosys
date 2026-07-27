from fastapi import Depends, Request
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.city import City
from models.firm_type import FirmType
from views.base import render_page


def firm_finder_page(request: Request, session: Session = Depends(get_session)):
    state, _ = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "crm", {"next": "/crm/firm_finder"})

    cities = session.exec(select(City).order_by(City.name)).all()
    firm_types = session.exec(select(FirmType).order_by(FirmType.name)).all()

    return render_page(
        request,
        "crm/firm_finder.html",
        "Поиск фирм",
        "crm",
        {"cities": cities, "firm_types": firm_types},
    )

"""
JSON API для управления баг-репортами в админке (используется JS на странице /admin/bugs).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from core.auth import resolve_admin_access
from db.database import get_session
from models.bug import Bug


logger = logging.getLogger("infosys.api.admin_bug")

router = APIRouter(prefix="/api/admin/bug", tags=["Admin - Баг-репорты"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class BugStateOut(BaseModel):
    id: int
    isopen: bool


@router.patch("/{bug_id}/toggle-open", response_model=BugStateOut)
def toggle_bug_open(
    bug_id: int, request: Request, session: Session = Depends(get_session)
) -> BugStateOut:
    _require_admin(request, session)

    target = session.get(Bug, bug_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Баг не найден.")

    target.isopen = not target.isopen
    session.add(target)
    session.commit()
    session.refresh(target)
    return BugStateOut(id=target.id, isopen=target.isopen)


@router.delete("/{bug_id}", status_code=204)
def delete_bug(bug_id: int, request: Request, session: Session = Depends(get_session)) -> None:
    _require_admin(request, session)

    target = session.get(Bug, bug_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Баг не найден.")

    session.delete(target)
    session.commit()

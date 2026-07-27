"""
JSON API для управления статусами задач (используется JS на странице /admin/taskstatus).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.auth import resolve_admin_access
from db.database import get_session
from models.task import Task
from models.task_status import TaskStatus


logger = logging.getLogger("infosys.api.task_status")

router = APIRouter(prefix="/api/admin/taskstatus", tags=["Admin - Статусы задач"])


def _require_admin(request: Request, session: Session) -> None:
    state, _ = resolve_admin_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Недостаточно прав для доступа к админке")


class TaskStatusIn(BaseModel):
    name: str = Field(..., min_length=1)


class TaskStatusOut(BaseModel):
    id: int
    name: str


@router.post("", response_model=TaskStatusOut, status_code=201)
def create_status(
    payload: TaskStatusIn, request: Request, session: Session = Depends(get_session)
) -> TaskStatusOut:
    _require_admin(request, session)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(select(TaskStatus).where(TaskStatus.name == name)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Статус «{name}» уже существует.")

    status = TaskStatus(name=name)
    session.add(status)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Статус «{name}» уже существует.")
    session.refresh(status)
    return TaskStatusOut(id=status.id, name=status.name)


@router.patch("/{status_id}", response_model=TaskStatusOut)
def rename_status(
    status_id: int,
    payload: TaskStatusIn,
    request: Request,
    session: Session = Depends(get_session),
) -> TaskStatusOut:
    _require_admin(request, session)

    target = session.get(TaskStatus, status_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Статус не найден.")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название не может быть пустым.")

    existing = session.exec(
        select(TaskStatus).where(TaskStatus.name == name, TaskStatus.id != status_id)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"Статус «{name}» уже существует.")

    target.name = name
    session.add(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Статус «{name}» уже существует.")
    session.refresh(target)
    return TaskStatusOut(id=target.id, name=target.name)


@router.delete("/{status_id}", status_code=204)
def delete_status(status_id: int, request: Request, session: Session = Depends(get_session)) -> None:
    _require_admin(request, session)

    target = session.get(TaskStatus, status_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Статус не найден.")

    in_use = session.exec(select(Task).where(Task.status_id == status_id)).first()
    if in_use is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить статус «{target.name}» — он используется в задачах.",
        )

    session.delete(target)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить статус «{target.name}» — он используется в задачах.",
        )

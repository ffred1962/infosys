"""
JSON API для управления задачами (используется JS на странице /crm/tasks).
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.task import Task
from models.task_status import TaskStatus
from models.users import User


logger = logging.getLogger("infosys.api.task")

router = APIRouter(prefix="/api/task", tags=["Задачи"])


def _require_authenticated(request: Request, session: Session) -> User:
    state, current_user = resolve_authenticated_access(request, session)
    if state != "ok":
        raise HTTPException(status_code=401, detail="Нужно войти в систему.")
    return current_user


def _get_owned_task_or_404(session: Session, task_id: int, user_id: int, owner_field: str) -> Task:
    """Загружает задачу, но не раскрывает разницу между "не существует" и "не твоя" — обе дают 404."""
    task = session.get(Task, task_id)
    if task is None or getattr(task, owner_field) != user_id:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    return task


class TaskTitleMixin(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Название не может быть пустым.")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskIn(TaskTitleMixin):
    """Создание задачи — автор выбирает всё, включая начальный статус."""

    due_date: datetime
    assignee_id: int
    status_id: int

    @field_validator("due_date")
    @classmethod
    def due_date_not_in_past(cls, value: datetime) -> datetime:
        if value.date() < datetime.utcnow().date():
            raise ValueError("Срок выполнения не может быть раньше сегодняшнего дня.")
        return value


class TaskEditIn(TaskTitleMixin):
    """Редактирование — только поля автора; status_id сюда намеренно не входит,
    его меняет исполнитель через /status, а не автор через этот эндпоинт."""

    due_date: datetime
    assignee_id: int


class TaskStatusChangeIn(BaseModel):
    status_id: int


class TaskOut(BaseModel):
    id: int
    creation_date: datetime
    author_id: int
    author_fullname: str
    assignee_id: int
    assignee_fullname: str
    title: str
    description: Optional[str]
    due_date: datetime
    status_id: int
    status_name: str
    completed: bool
    date_finished: Optional[datetime]


def _to_task_out(session: Session, task: Task) -> TaskOut:
    author = session.get(User, task.author_id)
    assignee = session.get(User, task.assignee_id)
    status = session.get(TaskStatus, task.status_id)
    return TaskOut(
        id=task.id,
        creation_date=task.creation_date,
        author_id=task.author_id,
        author_fullname=author.fullname,
        assignee_id=task.assignee_id,
        assignee_fullname=assignee.fullname,
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        status_id=task.status_id,
        status_name=status.name,
        completed=task.completed,
        date_finished=task.date_finished,
    )


def _validate_assignee(session: Session, assignee_id: int) -> None:
    if session.get(User, assignee_id) is None:
        raise HTTPException(status_code=404, detail="Исполнитель не найден.")


def _validate_status(session: Session, status_id: int) -> None:
    if session.get(TaskStatus, status_id) is None:
        raise HTTPException(status_code=404, detail="Статус не найден.")


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskIn, request: Request, session: Session = Depends(get_session)
) -> TaskOut:
    current_user = _require_authenticated(request, session)
    _validate_assignee(session, payload.assignee_id)
    _validate_status(session, payload.status_id)

    task = Task(
        author_id=current_user.id,
        assignee_id=payload.assignee_id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        status_id=payload.status_id,
    )
    session.add(task)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Не удалось создать задачу — проверьте исполнителя и статус.")
    session.refresh(task)

    return _to_task_out(session, task)


@router.patch("/{task_id}", response_model=TaskOut)
def edit_task(
    task_id: int, payload: TaskEditIn, request: Request, session: Session = Depends(get_session)
) -> TaskOut:
    current_user = _require_authenticated(request, session)
    task = _get_owned_task_or_404(session, task_id, current_user.id, "author_id")

    _validate_assignee(session, payload.assignee_id)
    # Оставить уже просроченный due_date как есть — можно (иначе нельзя было бы
    # поправить даже название у просроченной задачи), а вот подвинуть его в
    # прошлое намеренно — нельзя, та же логика, что и при создании.
    if payload.due_date != task.due_date and payload.due_date.date() < datetime.utcnow().date():
        raise HTTPException(
            status_code=422, detail="Срок выполнения не может быть раньше сегодняшнего дня."
        )

    task.title = payload.title
    task.description = payload.description
    task.due_date = payload.due_date
    task.assignee_id = payload.assignee_id
    session.add(task)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Не удалось сохранить задачу — проверьте исполнителя.")
    session.refresh(task)

    return _to_task_out(session, task)


@router.patch("/{task_id}/status", response_model=TaskOut)
def change_task_status(
    task_id: int,
    payload: TaskStatusChangeIn,
    request: Request,
    session: Session = Depends(get_session),
) -> TaskOut:
    current_user = _require_authenticated(request, session)
    task = _get_owned_task_or_404(session, task_id, current_user.id, "assignee_id")

    _validate_status(session, payload.status_id)

    task.status_id = payload.status_id
    session.add(task)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Не удалось сменить статус.")
    session.refresh(task)

    return _to_task_out(session, task)


@router.patch("/{task_id}/complete", response_model=TaskOut)
def toggle_task_complete(
    task_id: int, request: Request, session: Session = Depends(get_session)
) -> TaskOut:
    current_user = _require_authenticated(request, session)
    task = _get_owned_task_or_404(session, task_id, current_user.id, "author_id")

    task.completed = not task.completed
    task.date_finished = datetime.utcnow() if task.completed else None
    session.add(task)
    session.commit()
    session.refresh(task)

    return _to_task_out(session, task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, request: Request, session: Session = Depends(get_session)) -> None:
    current_user = _require_authenticated(request, session)
    task = _get_owned_task_or_404(session, task_id, current_user.id, "author_id")

    session.delete(task)
    session.commit()

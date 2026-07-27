"""
Модель задачи.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class Task(SQLModel, table=True):
    """Задача."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creation_date: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    author_id: int = Field(foreign_key="user.id", index=True)
    assignee_id: int = Field(foreign_key="user.id", index=True)
    title: str
    description: Optional[str] = None
    due_date: datetime = Field(index=True)
    status_id: int = Field(foreign_key="task_status.id", index=True)
    completed: bool = Field(default=False)
    date_finished: Optional[datetime] = Field(default=None, index=True)

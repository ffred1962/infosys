"""
Модель статуса задачи.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class TaskStatus(SQLModel, table=True):
    """Статус задачи."""

    __tablename__ = "task_status"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

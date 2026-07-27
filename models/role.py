"""
Модель роли пользователя.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class Role(SQLModel, table=True):
    """Роль пользователя."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

"""
Модель единицы измерения.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class Unit(SQLModel, table=True):
    """Единица измерения (шт, м, м2, ...)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

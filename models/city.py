"""
Модель города.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class City(SQLModel, table=True):
    """Город."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

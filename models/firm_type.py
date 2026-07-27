"""
Модель типа фирмы.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class FirmType(SQLModel, table=True):
    """Тип фирмы."""

    __tablename__ = "firm_type"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

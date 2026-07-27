"""
Модель системной константы (ключ/значение).
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class Constant(SQLModel, table=True):
    """Системная константа: name -> value, с отметкой времени последнего изменения."""

    __tablename__ = "constants"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    value: str
    updated: datetime = Field(default_factory=datetime.utcnow, index=True)

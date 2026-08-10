"""
Модель фирмы, найденной в результате поиска.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class Firm(SQLModel, table=True):
    """Фирма, найденная поиском по городу и типу."""

    id: Optional[int] = Field(default=None, primary_key=True)
    city_id: int = Field(foreign_key="city.id", index=True)
    type_id: int = Field(foreign_key="firm_type.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    creation_date: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    # Диапазон 0-10 проверяется на уровне API (Pydantic ge/le в FirmMutateMixin,
    # api/firm.py), не CHECK-constraint'ом в БД — тот же подход, что и у прочих
    # проверок в этом проекте (например due_date у Task). server_default нужен,
    # чтобы ALTER TABLE на уже заполненной таблице firm не упал на NOT NULL.
    rating: int = Field(default=5, index=True, sa_column_kwargs={"server_default": "5"})

"""
Модель категории поиска компаний-партнёров.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchCategory(SQLModel, table=True):
    """Категория поиска (например, магазины дверей, застройщики)."""

    __tablename__ = "search_category"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    label_ru: str
    target_count: int
    important: Optional[str] = None

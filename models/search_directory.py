"""
Модель каталога/справочника для поиска компаний по категории.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchDirectory(SQLModel, table=True):
    """Каталог, справочник или агрегатор, привязанный к категории поиска."""

    __tablename__ = "search_directory"

    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="search_category.id", index=True)
    name: str
    url_example: Optional[str] = None
    query_hint: Optional[str] = None
    try_direct_fetch: Optional[bool] = None
    notes: Optional[str] = None
    position: int

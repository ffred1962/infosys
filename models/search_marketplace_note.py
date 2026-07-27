"""
Модель заметки о маркетплейсах/соцсетях для категории поиска.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchMarketplaceNote(SQLModel, table=True):
    """Заметка о маркетплейсе или соцсети, привязанная к категории поиска."""

    __tablename__ = "search_marketplace_note"

    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="search_category.id", index=True)
    note: str
    position: int

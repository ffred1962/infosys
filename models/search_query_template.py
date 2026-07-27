"""
Модель шаблона поискового запроса для категории поиска.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchQueryTemplate(SQLModel, table=True):
    """Шаблон поискового запроса, привязанный к категории поиска."""

    __tablename__ = "search_query_template"

    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="search_category.id", index=True)
    template: str
    position: int

"""
Модель шаблона поискового запроса для поисковой системы общего назначения.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchEngineQueryTemplate(SQLModel, table=True):
    """Шаблон поискового запроса, привязанный к поисковой системе общего назначения."""

    __tablename__ = "search_engine_query_template"

    id: Optional[int] = Field(default=None, primary_key=True)
    engine_id: int = Field(foreign_key="search_engine.id", index=True)
    template: str
    position: int

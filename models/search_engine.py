"""
Модель поисковой системы/сервиса общего назначения.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchEngine(SQLModel, table=True):
    """Поисковая система или сервис общего назначения (не привязан к категории)."""

    __tablename__ = "search_engine"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    notes: Optional[str] = None
    url_template: Optional[str] = None
    position: int

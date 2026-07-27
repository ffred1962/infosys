"""
Модель общей заметки о методологии поиска источников (не привязана к категории).
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class SearchSourceNote(SQLModel, table=True):
    """Общая заметка о методологии поиска (например, дисклеймер или примечание про Yandex)."""

    __tablename__ = "search_source_note"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    content: str

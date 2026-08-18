"""
Модель статуса рассмотрения анкеты партнёра.
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class ApplicationState(SQLModel, table=True):
    """Статус рассмотрения анкеты партнёра (PartnerApplication.status_id) —
    та же форма справочной таблицы, что и TaskStatus, но по явной просьбе
    таблица называется во множественном числе (как и Constant -> constants),
    а не application_status."""

    __tablename__ = "application_states"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

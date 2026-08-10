"""
Модель примечания к фирме — простой append-only журнал (без редактирования и
удаления), см. "Примечания" на карточке фирмы (/crm/firms/{id}/comments).
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class FirmComment(SQLModel, table=True):
    """Примечание к фирме."""

    __tablename__ = "firm_comment"

    id: Optional[int] = Field(default=None, primary_key=True)
    added: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    user_id: int = Field(foreign_key="user.id", index=True)
    firm_id: int = Field(foreign_key="firm.id", index=True)
    comment: str

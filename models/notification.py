"""
Модель уведомления.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class Notification(SQLModel, table=True):
    """Уведомление."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creation_date: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    creator_id: int = Field(foreign_key="user.id", index=True)
    receiver_id: int = Field(foreign_key="user.id", index=True)
    msg: str
    viewed: bool = Field(default=False)

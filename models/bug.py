"""
Модель бага.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class Bug(SQLModel, table=True):
    """Баг."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creation_date: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    title: str
    reporter_id: int = Field(foreign_key="user.id", index=True)
    isopen: bool = Field(default=True)

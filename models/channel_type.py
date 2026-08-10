"""
Модель типа канала связи (email, мессенджеры и т.п.).
"""

from typing import Optional
from sqlmodel import Field, SQLModel


class ChannelType(SQLModel, table=True):
    """Тип канала связи с контактом/фирмой."""

    __tablename__ = "channel_type"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    is_active: bool = Field(default=True)
    is_input: bool = Field(default=True)
    is_output: bool = Field(default=True)
    icon_url: str

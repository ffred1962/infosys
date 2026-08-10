"""
Модель канала связи фирмы — конкретный контакт (адрес/номер/юзернейм) для
одного из справочных типов каналов (channel_type). У одной фирмы может быть
несколько каналов одного типа с разными адресами — намеренно нет уникального
ограничения на (firm_id, channel_id).
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class FirmChannel(SQLModel, table=True):
    """Канал связи фирмы."""

    __tablename__ = "firm_channel"

    id: Optional[int] = Field(default=None, primary_key=True)
    firm_id: int = Field(foreign_key="firm.id", index=True)
    channel_id: int = Field(foreign_key="channel_type.id", index=True)
    address: str
    description: Optional[str] = None
    date_added: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
    )

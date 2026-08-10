from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Field, SQLModel


class FirmEvent(SQLModel, table=True):
    """Событие, привязанное к конкретному каналу связи фирмы (не к самой фирме
    напрямую) — см. api/firm.py: firm_id для страницы/API выводится через join
    channel_id -> firm_channel.firm_id. Обратите внимание, что "channel_id" здесь
    указывает на строку firm_channel.id (конкретный канал связи фирмы, например
    "телефон +380..."), а не на channel_type.id, как одноимённое поле в
    FirmChannel — так задано в исходной спецификации таблицы."""

    __tablename__ = "firm_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    channel_id: int = Field(foreign_key="firm_channel.id", index=True)
    # Не индексируем created — так же, как FirmChannel.date_added: в исходной
    # спецификации таблицы это поле не было помечено "indexed" (в отличие от
    # channel_id/user_id, которые помечены явно).
    created: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
    )
    user_id: int = Field(foreign_key="user.id", index=True)
    description: str

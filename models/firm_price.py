"""
Модель прайс-листа фирмы (заголовок/версия на дату; сами товары и цены — в другой таблице).
"""

from datetime import date, datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class FirmPrice(SQLModel, table=True):
    """Прайс-лист фирмы: дата + примечание."""

    __tablename__ = "firm_price"

    id: Optional[int] = Field(default=None, primary_key=True)
    firm_id: int = Field(foreign_key="firm.id", index=True)
    created: date = Field(
        default_factory=lambda: datetime.utcnow().date(),
        sa_column_kwargs={"server_default": func.current_date()},
        index=True,
    )
    rem: Optional[str] = None

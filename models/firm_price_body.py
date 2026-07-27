"""
Модель строки прайс-листа фирмы (товар + цена в рамках конкретного прайс-листа).
"""

from decimal import Decimal
from typing import Optional
from sqlalchemy import Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


class FirmPriceBody(SQLModel, table=True):
    """Строка прайс-листа: товар и его цена (товар уникален в рамках прайс-листа)."""

    __tablename__ = "firm_price_body"
    __table_args__ = (
        UniqueConstraint("price_id", "good_id", name="uq_firm_price_body_price_id_good_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    price_id: int = Field(foreign_key="firm_price.id", index=True)
    good_id: int = Field(foreign_key="firm_goods.id", index=True)
    price: Decimal = Field(sa_type=Numeric(10, 2))

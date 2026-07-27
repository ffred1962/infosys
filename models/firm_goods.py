"""
Модель товара фирмы.
"""

from typing import Optional
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class FirmGoods(SQLModel, table=True):
    """Товар, принадлежащий фирме (артикул уникален в рамках фирмы)."""

    __tablename__ = "firm_goods"
    __table_args__ = (UniqueConstraint("firm_id", "article", name="uq_firm_goods_firm_id_article"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    firm_id: int = Field(foreign_key="firm.id", index=True)
    article: str = Field(index=True)
    name: str = Field(index=True)
    unit_id: int = Field(foreign_key="unit.id", index=True)

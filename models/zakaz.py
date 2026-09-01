"""
Модель заказа — импортирована из выгрузки 1С "Путевые листы"/"Реализация
товаров и услуг" (Контрагенты по ДАП). Один Zakaz — один документ
реализации, привязан к конкретной анкете контрагента (PartnerApplication)
через anketa_id. См. CLAUDE.md, раздел про импорт заказов и анкет из 1С.
"""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Zakaz(SQLModel, table=True):
    """Заказ (документ реализации)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    num: str = Field(index=True, unique=True)  # № заказа, например ДПА00000001
    ord_date: date = Field(index=True)
    city_id: int = Field(foreign_key="city.id", index=True)
    delivery_addr: str
    anketa_id: int = Field(foreign_key="partner_application.id", index=True)

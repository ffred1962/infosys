"""
Модель анкеты потенциального партнёра — публичная форма на /anketa (без
регистрации/входа в систему), по которой заявитель сам описывает себя, чтобы
получить статус партнёра/скидку/бесплатный образец. Первый шаг к AI-агенту
квалификации и верификации партнёров, описанному в anketa.docx — сейчас без
самого агента, только сбор данных + просмотр в админке.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Field, SQLModel


CUSTOMER_SEGMENT_OPTIONS = ("Эконом", "Средний", "Премиальный", "Не знаю")


class PartnerApplication(SQLModel, table=True):
    """Анкета потенциального партнёра — одна запись на одну публичную отправку
    формы /anketa. Ни к какому User не привязана (заявитель не авторизован)."""

    __tablename__ = "partner_application"

    id: Optional[int] = Field(default=None, primary_key=True)
    created: datetime = Field(
        default_factory=datetime.utcnow,
        index=True,
        sa_column_kwargs={"server_default": func.now()},
    )

    full_name: str
    phone: str
    email: Optional[str] = None

    # Заявленный тип клиента — переиспользуем существующий справочник
    # firm_type (магазин дверей/дизайн студия/установщик дверей/...), а не
    # заводим отдельный список: это тот же классификатор "кто это", что и у
    # найденных через поиск фирм, дублировать его отдельной таблицей/списком
    # не нужно.
    claimed_type_id: int = Field(foreign_key="firm_type.id", index=True)

    company_name: Optional[str] = None
    company_website: Optional[str] = None
    activity_type: Optional[str] = None

    # Город — предпочтительно ссылка на существующий справочник City; если
    # заявитель не нашёл свой город в списке, city_id остаётся пустым, а
    # свободный текст сохраняется в city_other. Осознанно НЕ создаём новую
    # запись в City прямо из публичной неаутентифицированной формы — этот
    # справочник используется по всему проекту (поиск фирм, графики, фильтры)
    # и до сих пор редактировался только через /admin/city под админом;
    # анонимная запись туда была бы первой дырой в этом правиле и открытым
    # вектором для спама справочника. Админ может завести город вручную при
    # просмотре анкеты, если сочтёт нужным.
    city_id: Optional[int] = Field(default=None, foreign_key="city.id", index=True)
    city_other: Optional[str] = None

    has_physical_office: Optional[bool] = None  # None = не указано/не знаю

    projects_description: Optional[str] = None
    projects_count: Optional[str] = None  # текстом, не int — «неизвестно»/«10-20» тоже валидный ответ
    customer_segment: Optional[str] = None  # одно из CUSTOMER_SEGMENT_OPTIONS

    wants_discount: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})
    wants_sample: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})

    comment: Optional[str] = None

    # Статус рассмотрения — ссылка на справочник ApplicationState
    # (models/application_state.py, таблица application_states), не строка:
    # тот же паттерн, что и Task.status_id -> task_status. Не заполняется
    # заявителем — routers/anketa.py:submit_anketa проставляет запись
    # "новая" сам при создании.
    status_id: int = Field(foreign_key="application_states.id", index=True)

    # Технические данные запроса — тот же приём, что и login_info
    # (core.auth.record_login_attempt): полезно при разборе подозрительных/
    # спам-заявок с полностью неаутентифицированной публичной формы.
    client_ip: Optional[str] = Field(default=None, index=True)
    user_agent: Optional[str] = None

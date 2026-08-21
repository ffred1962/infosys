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

    # Поля ниже добавлены по итогам повторного просмотра anketa.docx — не для
    # собственной логики скоринга (сам AI-агент верификации туда пока не
    # реализован, это по-прежнему только сбор данных), а как "затравка" для
    # его будущих модулей Organization/Business Verification: соцсети и
    # текущие бренды — прямые сигналы, которые документ явно называет
    # источником проверки принадлежности/коммерческого влияния; лет на рынке
    # и число сотрудников — пункты того же чек-листа для Office & Exposure
    # Verification. Все — необязательный свободный текст, тем же приёмом,
    # что и projects_count («не знаю» — валидный ответ).
    #
    # Соцсети изначально были одним полем social_media; разбиты на три
    # отдельных по прямому запросу пользователя — так проще и заявителю
    # заполнять, и админу/будущему AI-агенту читать конкретную ссылку, не
    # разбирая свободный текст с несколькими URL внутри.
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    linkedin: Optional[str] = None
    years_in_business: Optional[str] = None
    team_size: Optional[str] = None
    current_brands: Optional[str] = None  # с какими брендами дверей уже работает/сотрудничает

    # ИНН (для ФОП) или ОКПО (для организаций) — по прямому запросу
    # пользователя при добавлении полей выше; одно поле на оба случая
    # (заявитель вписывает то, что у него есть), не валидируется по формату/
    # контрольной сумме — это просто заявленное значение для будущей ручной/
    # AI-проверки, не юридически значимая ИНН-верификация.
    tax_id: Optional[str] = None

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

    # Внутренняя проверка админом — не показывается заявителю нигде на
    # публичной стороне (/anketa, /anketa/submit), только в карточке анкеты
    # в /admin/partner_applications. Одна форма сохранения на статус+заметки
    # (api/admin_partner_applications.py: PATCH .../review) выставляет
    # verified_by/last_changed сама при каждом сохранении — оба поля никогда
    # не передаются с клиента напрямую, тот же приём, что и Constant.updated.
    verification_notes: Optional[str] = None
    verified_by: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    last_changed: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
    )

from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv

# Грузим .env раньше импорта db.database — так же, как main.py делает это перед
# импортом core.auth (см. комментарий там). Без этого `alembic` из командной
# строки не увидит DATABASE_URL из .env (в отличие от db.migrate.upgrade_to_head(),
# который main.py вызывает уже ПОСЛЕ своего load_dotenv()) и всегда мигрировал
# бы локальный SQLite, даже когда приложение сконфигурировано на внешнюю БД.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlmodel import SQLModel as BaseSQLModel
import models.users  # Import models to register them with SQLModel.metadata
import models.role
import models.user_role
import models.task_status
import models.task
import models.city
import models.firm_type
import models.bug
import models.notification
import models.search_category
import models.search_query_template
import models.search_directory
import models.search_marketplace_note
import models.search_engine
import models.search_engine_query_template
import models.search_source_note
import models.firm
import models.unit
import models.constants
import models.firm_goods
import models.firm_price
import models.firm_price_body
import models.login_info
import models.firm_comment
import models.channel_type
import models.firm_channel
import models.firm_event
import models.application_state
import models.partner_application

from alembic import context
from db.database import DB_URL

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# db.database.DB_URL — единственный источник правды по адресу БД (сам решает,
# SQLite по умолчанию или DATABASE_URL из .env/окружения) — переопределяем им
# статичный sqlalchemy.url из alembic.ini, чтобы alembic (что при ручном
# вызове, что при db.migrate.upgrade_to_head() из main.py) всегда мигрировал
# ту же БД, к которой подключается само приложение, а не рассинхронизировался.
config.set_main_option("sqlalchemy.url", DB_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from models.base import SQLModel as BaseSQLModel
target_metadata = BaseSQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
Программный запуск `alembic upgrade head`.

Нужен для облачного/эфемерного деплоя: если на инстансе ещё нет
data/infosys.db (или есть, но пустой — с нуля созданный SQLAlchemy-движком
файл без единой таблицы), приложение раньше падало на первом же запросе к БД
("no such table: user") вместо того, чтобы просто накатить миграции. Локально
это не проблема (data/infosys.db уже смигрирован и лежит в рабочей копии),
но идемпотентный upgrade("head") там тоже безопасен — если БД уже на head,
alembic просто ничего не делает.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def upgrade_to_head() -> None:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")

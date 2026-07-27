"""
Конфигурация подключения к БД и сессия.
"""

import os
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool


# Путь к БД (SQLite в папке data/)
DB_DIR = "data"
os.makedirs(DB_DIR, exist_ok=True)
DB_URL = f"sqlite:///{DB_DIR}/infosys.db"

# Движок (для SQLite используем StaticPool для избежания проблем с threading)
engine = create_engine(
    DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite игнорирует внешние ключи, пока это не включено явно на каждом соединении."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_and_tables():
    """Создаёт все таблицы из моделей."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Генератор сессии для зависимостей FastAPI."""
    with Session(engine) as session:
        yield session

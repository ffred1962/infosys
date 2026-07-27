"""
Конфигурация подключения к БД и сессия.
"""

import os
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool


# Путь к локальной БД (SQLite в папке data/) — используется, если DATABASE_URL
# не задана в окружении.
DB_DIR = "data"
os.makedirs(DB_DIR, exist_ok=True)
SQLITE_DB_URL = f"sqlite:///{DB_DIR}/infosys.db"

# DATABASE_URL (.env) переключает на внешнюю БД (например, Postgres) без
# изменений кода. Не задана — работаем как раньше, на локальном SQLite-файле;
# это же и путь назад — просто убрать/закомментировать DATABASE_URL в .env.
DB_URL = os.environ.get("DATABASE_URL", SQLITE_DB_URL)
IS_SQLITE = DB_URL.startswith("sqlite")

if IS_SQLITE:
    # StaticPool + check_same_thread=False — обход проблем SQLite с threading
    # (один физический файл, один и тот же соединение переиспользуется).
    # Для настоящей серверной БД (Postgres и т.п.) это не нужно и вредно —
    # там должен работать обычный пул соединений SQLAlchemy.
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
else:
    engine = create_engine(DB_URL, echo=False)


def create_db_and_tables():
    """Создаёт все таблицы из моделей."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Генератор сессии для зависимостей FastAPI."""
    with Session(engine) as session:
        yield session

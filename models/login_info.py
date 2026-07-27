"""
Модель попытки входа в систему (успешной и неуспешной) — для аудита.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class LoginInfo(SQLModel, table=True):
    """Попытка авторизации."""

    __tablename__ = "login_info"

    id: Optional[int] = Field(default=None, primary_key=True)
    created: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    client_ip: str = Field(index=True)
    user_agent: str
    status: str

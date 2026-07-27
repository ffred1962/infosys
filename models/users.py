"""
Модель пользователя.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, func


class User(SQLModel, table=True):
    """Пользователь приложения."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    fullname: str
    name: str
    passwordhash: str
    creation_date: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()},
        index=True,
    )
    isactive: bool = Field(default=True)

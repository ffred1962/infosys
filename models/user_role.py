"""
Связь пользователей и ролей (многие-ко-многим).
"""

from sqlmodel import Field, SQLModel


class UserRole(SQLModel, table=True):
    """Назначение роли пользователю."""

    __tablename__ = "user_role"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)

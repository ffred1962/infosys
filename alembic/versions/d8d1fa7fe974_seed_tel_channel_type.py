"""seed tel channel type

Revision ID: d8d1fa7fe974
Revises: 4c60c39b3918
Create Date: 2026-08-10 13:02:34.692653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd8d1fa7fe974'
down_revision: Union[str, Sequence[str], None] = '4c60c39b3918'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


channel_type_table = sa.table(
    'channel_type',
    sa.column('name', sqlmodel.sql.sqltypes.AutoString()),
    sa.column('is_active', sa.Boolean()),
    sa.column('is_input', sa.Boolean()),
    sa.column('is_output', sa.Boolean()),
    sa.column('icon_url', sqlmodel.sql.sqltypes.AutoString()),
)


def upgrade() -> None:
    """Upgrade schema."""
    # Данные, а не схема — добавляем один тип канала (tel) вдогонку к 6,
    # засеянным в 4c60c39b3918_add_channel_type_table.py.
    op.bulk_insert(channel_type_table, [
        {'name': 'tel', 'is_active': True, 'is_input': True, 'is_output': True, 'icon_url': '/pic/tel.svg'},
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(channel_type_table.delete().where(channel_type_table.c.name == 'tel'))

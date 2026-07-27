"""rename user creationdate to creation_date and add task completed default

Revision ID: b4f5ccab0c24
Revises: 035d8103cf9f
Create Date: 2026-07-15 10:25:57.298773

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f5ccab0c24'
down_revision: Union[str, Sequence[str], None] = '035d8103cf9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'creationdate',
            new_column_name='creation_date',
            existing_type=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text('(CURRENT_TIMESTAMP)'),
        )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_creation_date'), ['creation_date'], unique=False)

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.alter_column(
            'completed',
            existing_type=sa.Boolean(),
            server_default=sa.false(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.alter_column(
            'completed',
            existing_type=sa.Boolean(),
            server_default=None,
            existing_nullable=False,
        )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_creation_date'))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'creation_date',
            new_column_name='creationdate',
            existing_type=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text('(CURRENT_TIMESTAMP)'),
        )

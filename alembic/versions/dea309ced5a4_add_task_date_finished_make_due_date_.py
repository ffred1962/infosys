"""add task.date_finished, make due_date required

Revision ID: dea309ced5a4
Revises: 07e4e837ac49
Create Date: 2026-07-16 11:48:09.165749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dea309ced5a4'
down_revision: Union[str, Sequence[str], None] = '07e4e837ac49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('task', sa.Column('date_finished', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_task_date_finished'), 'task', ['date_finished'], unique=False)

    # SQLite can't ALTER COLUMN directly; use batch mode so the index on
    # due_date is preserved across the table recreation.
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.alter_column(
            "due_date",
            existing_type=sa.DATETIME(),
            nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.alter_column(
            "due_date",
            existing_type=sa.DATETIME(),
            nullable=True,
        )

    op.drop_index(op.f('ix_task_date_finished'), table_name='task')
    op.drop_column('task', 'date_finished')

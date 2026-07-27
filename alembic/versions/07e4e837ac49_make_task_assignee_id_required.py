"""make task.assignee_id required

Revision ID: 07e4e837ac49
Revises: 6de2fad05329
Create Date: 2026-07-16 11:42:37.681304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07e4e837ac49'
down_revision: Union[str, Sequence[str], None] = '6de2fad05329'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite can't ALTER COLUMN directly; use batch mode so the FK and index
    # on assignee_id are preserved across the table recreation.
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.alter_column(
            "assignee_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.alter_column(
            "assignee_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

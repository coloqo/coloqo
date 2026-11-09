"""task delivery: a task's meaning in the business's language, and tasks working for it

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-09 23:30:00.000000

Decision 0036: a delivery is a text field of the task; another task may work for it.
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column("tasks", sa.Column("delivery", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "tasks",
        sa.Column(
            "works_for_id",
            sa.Integer(),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_tasks_works_for_id", "tasks", ["works_for_id"])


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index("ix_tasks_works_for_id", table_name="tasks")
    op.drop_column("tasks", "works_for_id")
    op.drop_column("tasks", "delivery")

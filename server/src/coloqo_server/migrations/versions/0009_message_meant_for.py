"""message meant for an offline session

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-21 20:00:00.000000

Decision 0029: a Message addressed to a session that is offline goes to its person, and keeps
which session it was meant for.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "messages",
        sa.Column(
            "meant_for_id",
            sa.Integer(),
            sa.ForeignKey("assistants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("messages", "meant_for_id")

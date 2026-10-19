"""message by holder

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19 23:30:00.000000

Who held a Topic earlier is not recorded, so existing Messages get the mark only when their
Assistant holds the Topic now.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "messages", sa.Column("by_holder", sa.Boolean(), server_default="false", nullable=False)
    )
    op.execute(
        "UPDATE messages SET by_holder = true FROM topics "
        "WHERE topics.id = messages.topic_id "
        "AND messages.author_assistant_id = topics.holder_assistant_id"
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("messages", "by_holder")

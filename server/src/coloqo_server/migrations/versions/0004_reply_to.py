"""reply to

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19 22:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column("messages", sa.Column("reply_to", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("messages", "reply_to")

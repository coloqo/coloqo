"""team time zone: the zone a Team's plans count their days in

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-10 02:00:00.000000

Decision 0037, refined: a plan's period is days of its Team, so the Team has a time zone; existing
Teams start in UTC until their owner chooses.
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "teams", sa.Column("time_zone", sa.String(64), nullable=False, server_default="UTC")
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("teams", "time_zone")

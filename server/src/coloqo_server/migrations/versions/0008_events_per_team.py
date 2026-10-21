"""events numbered per team

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-21 12:00:00.000000

Decision 0028: an event is stored once for its Team and numbered in it; a stream's cursor names
a number per Team instead of a database id. The log is a week-long signal, not content, so it
starts anew in both directions: a client with an old cursor gets new events and re-reads.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("DELETE FROM events")
    op.drop_index("ix_events_user_id_id", table_name="events")
    op.drop_column("events", "user_id")
    op.add_column(
        "events",
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
    )
    op.add_column("events", sa.Column("number", sa.Integer(), nullable=False))
    op.create_unique_constraint("events_team_id_number_key", "events", ["team_id", "number"])
    op.add_column(
        "teams", sa.Column("last_event", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    """Revert the migration."""
    op.execute("DELETE FROM events")
    op.drop_column("teams", "last_event")
    op.drop_constraint("events_team_id_number_key", "events", type_="unique")
    op.drop_column("events", "number")
    op.drop_column("events", "team_id")
    op.add_column(
        "events",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
    )
    op.create_index("ix_events_user_id_id", "events", ["user_id", "id"])

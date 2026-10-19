"""linked assistants, task topics, retention, avatars

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20 01:00:00.000000

Decisions 0019 (avatars), 0020 (an Assistant linked to one Team), 0021 (stage and closing
Messages, the archive). An existing Assistant is linked to the Team it wrote or held Topics in,
when that is exactly one Team its person still belongs to. Downgrading keeps the two new values
of ``message_kind``: PostgreSQL cannot drop an enum value.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("ALTER TYPE message_kind ADD VALUE IF NOT EXISTS 'stage'")
    op.execute("ALTER TYPE message_kind ADD VALUE IF NOT EXISTS 'closed'")
    op.add_column("users", sa.Column("avatar_version", sa.Integer(), nullable=True))
    op.add_column("assistants", sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "assistants_team_id_fkey", "assistants", "teams", ["team_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("teams", sa.Column("archive_days", sa.Integer(), nullable=True))
    for column in ("closed_at", "idle_warned_at", "deleted_at"):
        op.add_column("topics", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "messages", sa.Column("system", sa.Boolean(), server_default="false", nullable=False)
    )
    op.execute("UPDATE topics SET closed_at = updated_at WHERE status = 'closed'")
    op.execute(
        """
        UPDATE assistants SET team_id = worked.team_id
        FROM (
            SELECT assistant_id, min(team_id) AS team_id FROM (
                SELECT messages.author_assistant_id AS assistant_id, topics.team_id
                FROM messages JOIN topics ON topics.id = messages.topic_id
                WHERE messages.author_assistant_id IS NOT NULL
                UNION
                SELECT holder_assistant_id, team_id FROM topics
                WHERE holder_assistant_id IS NOT NULL
            ) AS both_ways
            GROUP BY assistant_id
            HAVING count(DISTINCT team_id) = 1
        ) AS worked
        WHERE assistants.id = worked.assistant_id
        AND EXISTS (
            SELECT 1 FROM members
            WHERE members.team_id = worked.team_id AND members.user_id = assistants.user_id
        )
        """
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("messages", "system")
    for column in ("deleted_at", "idle_warned_at", "closed_at"):
        op.drop_column("topics", column)
    op.drop_column("teams", "archive_days")
    op.drop_constraint("assistants_team_id_fkey", "assistants", type_="foreignkey")
    op.drop_column("assistants", "team_id")
    op.drop_column("users", "avatar_version")

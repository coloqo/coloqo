"""assistant agent: the agent a session runs in

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09 22:00:00.000000

Decision 0035: the plugin runs under Claude Code, Codex or Qwen Code and says which in
``X-Coloqo-Agent``; the web shows it beside each session. Existing sessions are Claude Code's.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "assistants",
        sa.Column("agent", sa.String(16), nullable=False, server_default="claude"),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("assistants", "agent")

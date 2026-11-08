"""boards and periods: the board's columns over stages, a promise's period

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08 23:00:00.000000

Decision 0032: a board is ordered columns, each a set of stages or the condition "has an active
external wait"; the first version shows one per Team, built when it is first asked for.
Decision 0031: a promise has a period.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

COLUMN_RULE = postgresql.ENUM("stages", "waiting", name="column_rule", create_type=False)


def upgrade() -> None:
    """Apply the migration."""
    COLUMN_RULE.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("main", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_boards_team_id", "boards", ["team_id"])
    op.create_table(
        "board_columns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "board_id", sa.Integer(), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("rule", COLUMN_RULE, nullable=False),
    )
    op.create_index("ix_board_columns_board_id", "board_columns", ["board_id"])
    op.create_table(
        "column_stages",
        sa.Column(
            "column_id",
            sa.Integer(),
            sa.ForeignKey("board_columns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("stages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "board_id", sa.Integer(), sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
        ),
        sa.UniqueConstraint("board_id", "stage_id"),
    )
    op.add_column("tasks", sa.Column("period_start", sa.Date(), nullable=True))
    op.add_column("tasks", sa.Column("period_end", sa.Date(), nullable=True))


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("tasks", "period_end")
    op.drop_column("tasks", "period_start")
    op.drop_table("column_stages")
    op.drop_table("board_columns")
    op.drop_table("boards")
    COLUMN_RULE.drop(op.get_bind(), checkfirst=True)

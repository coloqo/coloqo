"""plans: a Team's plan for a period, its rows and marks; whether a task's source was named

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-10 00:30:00.000000

Decision 0037: a plan is a draft until a human approves it and closed by a human after its period;
it holds promises and tasks, each row with a mark set by itself and possibly postponed; a task's
source makes a row found only when its creator named it.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

PLAN_MARK = postgresql.ENUM("planned", "found", "off_plan", name="plan_mark", create_type=False)
PLAN_RESULT = postgresql.ENUM(
    "done", "cancelled", "not_done", name="plan_result", create_type=False
)


def upgrade() -> None:
    """Apply the migration."""
    PLAN_MARK.create(op.get_bind(), checkfirst=True)
    PLAN_RESULT.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tasks", sa.Column("source_given", sa.Boolean(), nullable=False, server_default="false")
    )
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("team_id", "number"),
    )
    op.create_index("ix_plans_team_id", "plans", ["team_id"])
    op.create_table(
        "plan_items",
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("mark", PLAN_MARK, nullable=False),
        sa.Column("dropped", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("postponed_at", sa.DateTime(timezone=True)),
        sa.Column("postponed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("postponed_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("result", PLAN_RESULT),
    )
    op.create_index("ix_plan_items_task_id", "plan_items", ["task_id"])


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index("ix_plan_items_task_id", table_name="plan_items")
    op.drop_table("plan_items")
    op.drop_index("ix_plans_team_id", table_name="plans")
    op.drop_table("plans")
    op.drop_column("tasks", "source_given")
    PLAN_RESULT.drop(op.get_bind(), checkfirst=True)
    PLAN_MARK.drop(op.get_bind(), checkfirst=True)

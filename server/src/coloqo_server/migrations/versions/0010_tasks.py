"""tasks: the tracker's data, and every Topic becomes a task

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-08 22:00:00.000000

Decisions 0030-0033. Workflows with stages, tasks, their links and timeline. Each Team gets the
built-in task and promise workflows, and its Areas point to the task one. Every existing Topic
becomes a task with the same number: a closed one done, an open one in analysis, the timeline
saying the migration set it; the Topic keeps its number in the free series, so its old links lead
to the task. Topics are no longer deleted by time, so a Team's archive days go.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

TASK_TYPE = postgresql.ENUM("task", "promise", name="task_type", create_type=False)
STAGE_KIND = postgresql.ENUM(
    "backlog",
    "analysis",
    "design",
    "documentation",
    "agreement",
    "code",
    "review",
    "delivery",
    "done",
    "cancelled",
    "draft",
    "given",
    "delivered",
    "not_delivered",
    "withdrawn",
    name="stage_kind",
    create_type=False,
)

TASK_STAGES = [
    ("Backlog", "backlog"),
    ("Analysis", "analysis"),
    ("Design", "design"),
    ("Documentation", "documentation"),
    ("Agreement", "agreement"),
    ("Code", "code"),
    ("Review", "review"),
    ("Delivery", "delivery"),
    ("Done", "done"),
    ("Cancelled", "cancelled"),
]
PROMISE_STAGES = [
    ("Draft", "draft"),
    ("Given", "given"),
    ("Delivered", "delivered"),
    ("Not delivered", "not_delivered"),
    ("Withdrawn", "withdrawn"),
]


def _values(stages: list[tuple[str, str]]) -> str:
    """Return the stages as an SQL ``VALUES`` list: name, kind, position.

    Args:
        stages: Names and kinds in order.
    """
    return ", ".join(
        f"('{name}', '{kind}'::stage_kind, {position})"
        for position, (name, kind) in enumerate(stages, start=1)
    )


def upgrade() -> None:
    """Apply the migration."""
    bind = op.get_bind()
    TASK_TYPE.create(bind, checkfirst=True)
    STAGE_KIND.create(bind, checkfirst=True)

    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("type", TASK_TYPE, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_workflows_team_id", "workflows", ["team_id"])
    op.create_table(
        "stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("kind", STAGE_KIND, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workflow_id", "name"),
    )
    op.create_index("ix_stages_workflow_id", "stages", ["workflow_id"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("type", TASK_TYPE, nullable=False),
        sa.Column(
            "area_id", sa.Integer(), sa.ForeignKey("areas.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "parent_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("stages.id"), nullable=False),
        sa.Column(
            "assignee_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("outcome", sa.Text(), nullable=False, server_default=""),
        sa.Column("waiting", sa.String(300), nullable=True),
        sa.Column("rank", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idle_noticed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("team_id", "number"),
    )
    op.create_index("ix_tasks_team_id", "tasks", ["team_id"])
    op.create_index("ix_tasks_area_id", "tasks", ["area_id"])
    op.create_table(
        "task_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("url", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_task_links_task_id", "task_links", ["task_id"])
    op.create_table(
        "task_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "author_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "author_assistant_id",
            sa.Integer(),
            sa.ForeignKey("assistants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])

    op.add_column("teams", sa.Column("last_task", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "teams", sa.Column("tracker", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "teams", sa.Column("task_idle_days", sa.Integer(), nullable=False, server_default="7")
    )
    op.add_column(
        "teams",
        sa.Column("task_idle_repeat_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "areas",
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "topics",
        sa.Column(
            "task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
        ),
    )
    op.create_unique_constraint("uq_topics_task_id", "topics", ["task_id"])
    op.alter_column("topics", "number", existing_type=sa.Integer(), nullable=True)

    # Every Team gets the built-in workflows; its Areas take the task one.
    op.execute("INSERT INTO workflows (team_id, type) SELECT id, 'task' FROM teams")
    op.execute("INSERT INTO workflows (team_id, type) SELECT id, 'promise' FROM teams")
    for type_, stages in (("task", TASK_STAGES), ("promise", PROMISE_STAGES)):
        op.execute(
            "INSERT INTO stages (workflow_id, name, kind, position) "
            "SELECT w.id, v.name, v.kind, v.position FROM workflows w "
            f"CROSS JOIN (VALUES {_values(stages)}) AS v(name, kind, position) "
            f"WHERE w.type = '{type_}'"
        )
    op.execute(
        "UPDATE areas SET workflow_id = w.id FROM workflows w "
        "WHERE w.team_id = areas.team_id AND w.type = 'task'"
    )

    # Every Topic becomes a task with its number: closed ones done, open ones in analysis.
    op.execute(
        "INSERT INTO tasks (team_id, number, type, area_id, title, description, stage_id, "
        "assignee_id, outcome, rank, created_by, created_at, updated_at, started_at, finished_at) "
        "SELECT t.team_id, t.number, 'task', t.area_id, t.title, '', s.id, "
        "COALESCE(h.user_id, t.created_by), t.outcome, t.number, t.created_by, t.created_at, "
        "t.updated_at, t.created_at, "
        "CASE WHEN t.status = 'closed' THEN COALESCE(t.closed_at, t.updated_at) END "
        "FROM topics t "
        "JOIN areas a ON a.id = t.area_id "
        "JOIN stages s ON s.workflow_id = a.workflow_id AND s.kind = "
        "(CASE WHEN t.status = 'closed' THEN 'done' ELSE 'analysis' END)::stage_kind "
        "LEFT JOIN assistants h ON h.id = t.holder_assistant_id"
    )
    op.execute(
        "UPDATE topics SET task_id = k.id FROM tasks k "
        "WHERE k.team_id = topics.team_id AND k.number = topics.number"
    )
    op.execute(
        "INSERT INTO task_links (task_id, key, url, created_at) "
        "SELECT task_id, left(issue, 100), "
        "CASE WHEN issue ~ '^https?://' THEN left(issue, 500) ELSE '' END, created_at "
        "FROM topics WHERE issue <> ''"
    )
    op.execute(
        "INSERT INTO task_events (task_id, kind, author_user_id, data, created_at) "
        "SELECT k.id, 'created', k.created_by, '{\"migrated\": true}'::jsonb, k.created_at "
        "FROM tasks k"
    )
    op.execute(
        "INSERT INTO task_events (task_id, kind, data, created_at) "
        "SELECT k.id, 'stage', jsonb_build_object('to', s.name, 'kind', s.kind::text, "
        "'migrated', true), k.created_at "
        "FROM tasks k JOIN stages s ON s.id = k.stage_id"
    )
    op.execute(
        "INSERT INTO task_events (task_id, kind, data, created_at) "
        "SELECT k.id, 'closed', jsonb_build_object('outcome', k.outcome, 'migrated', true), "
        "k.finished_at FROM tasks k WHERE k.finished_at IS NOT NULL"
    )
    op.execute("UPDATE teams SET last_task = last_topic")

    # Topics are kept (decision 0030).
    op.drop_column("teams", "archive_days")


def downgrade() -> None:
    """Revert the migration: the tasks go; a task's Topic made since gets a free number."""
    op.add_column("teams", sa.Column("archive_days", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE topics SET number = t.last_topic + n.position FROM teams t, "
        "(SELECT id, row_number() OVER (PARTITION BY team_id ORDER BY id) AS position "
        "FROM topics WHERE number IS NULL) AS n "
        "WHERE n.id = topics.id AND t.id = topics.team_id"
    )
    op.execute(
        "UPDATE teams SET last_topic = COALESCE("
        "(SELECT max(number) FROM topics WHERE topics.team_id = teams.id), 0)"
    )
    op.alter_column("topics", "number", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("uq_topics_task_id", "topics", type_="unique")
    op.drop_column("topics", "task_id")
    op.drop_column("areas", "workflow_id")
    op.drop_column("teams", "task_idle_repeat_days")
    op.drop_column("teams", "task_idle_days")
    op.drop_column("teams", "tracker")
    op.drop_column("teams", "last_task")
    op.drop_table("task_events")
    op.drop_table("task_links")
    op.drop_table("tasks")
    op.drop_table("stages")
    op.drop_table("workflows")
    bind = op.get_bind()
    STAGE_KIND.drop(bind, checkfirst=True)
    TASK_TYPE.drop(bind, checkfirst=True)

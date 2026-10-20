"""sessions as assistants, slugs, per-team numbers, the human's part

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20 22:00:00.000000

Decisions 0024 (an Assistant is a session), 0025 (slugs, per-Team numbering, public keys) and
0026 (the human's part in a reply). The data is kept: each Assistant's project becomes a Project
holding its Team link, and the Assistant stays as the one session a plugin without sessions
registers (``session_key`` empty), with a word added to its name; Teams and Areas get slugs from
their names; Topics and files are numbered per Team in their old order; a relayed Message is
"the human's words", other replies stay unmarked, since how they were made is unknown.

Downgrading keeps the earliest Assistant of each project, moves the others' Messages, Topics and
files to it and drops them, turns "taken" lines into stage lines, and keeps the ``human_part``
type and the ``taken`` value of ``message_kind``: PostgreSQL cannot drop an enum value.
"""

import secrets
import string

import sqlalchemy as sa
from alembic import op

from coloqo_server.naming import WORDS, numbered, slugify

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

KEY_ALPHABET = string.ascii_lowercase + string.digits


def _key() -> str:
    """Return a random public key, as ``naming.new_key`` makes them: a letter first."""
    return secrets.choice(string.ascii_lowercase) + "".join(
        secrets.choice(KEY_ALPHABET) for _ in range(11)
    )


def upgrade() -> None:
    """Apply the migration."""
    bind = op.get_bind()
    op.execute("ALTER TYPE message_kind ADD VALUE IF NOT EXISTS 'taken'")

    op.add_column("installations", sa.Column("key", sa.String(16), nullable=True))
    for (installation_id,) in bind.execute(sa.text("SELECT id FROM installations")).all():
        bind.execute(
            sa.text("UPDATE installations SET key = :key WHERE id = :id"),
            {"key": _key(), "id": installation_id},
        )
    op.alter_column("installations", "key", nullable=False)
    op.create_unique_constraint("installations_key_key", "installations", ["key"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("installations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("installation_id", "project_key"),
    )
    op.add_column("assistants", sa.Column("key", sa.String(16), nullable=True))
    op.add_column(
        "assistants",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
    )
    op.add_column(
        "assistants", sa.Column("session_key", sa.String(64), server_default="", nullable=False)
    )
    op.add_column("assistants", sa.Column("session_id", sa.String(100), nullable=True))
    op.add_column("assistants", sa.Column("word", sa.String(32), nullable=True))
    op.alter_column("assistants", "name", type_=sa.String(130))
    rows = bind.execute(
        sa.text(
            "SELECT id, user_id, installation_id, project_key, name, team_id, created_at "
            "FROM assistants ORDER BY id"
        )
    ).all()
    for index, row in enumerate(rows):
        _, _, folder = row.name.partition(" · ")
        project_id = bind.execute(
            sa.text(
                "INSERT INTO projects (key, user_id, installation_id, project_key, name, team_id, "
                "created_at) VALUES (:key, :user_id, :installation_id, :project_key, :name, "
                ":team_id, :created_at) RETURNING id"
            ),
            {
                "key": _key(),
                "user_id": row.user_id,
                "installation_id": row.installation_id,
                "project_key": row.project_key,
                "name": (folder or "project")[:60],
                "team_id": row.team_id,
                "created_at": row.created_at,
            },
        ).scalar_one()
        word = WORDS[index % len(WORDS)]
        bind.execute(
            sa.text(
                "UPDATE assistants SET key = :key, project_id = :project_id, word = :word, "
                "name = :name WHERE id = :id"
            ),
            {
                "key": _key(),
                "project_id": project_id,
                "word": word,
                "name": f"{row.name} · {word}",
                "id": row.id,
            },
        )
    for column in ("key", "project_id", "word"):
        op.alter_column("assistants", column, nullable=False)
    op.create_unique_constraint("assistants_key_key", "assistants", ["key"])
    op.drop_constraint("assistants_installation_id_project_key_key", "assistants", type_="unique")
    op.create_unique_constraint(
        "assistants_project_id_session_key_key", "assistants", ["project_id", "session_key"]
    )
    op.drop_constraint("assistants_team_id_fkey", "assistants", type_="foreignkey")
    op.drop_column("assistants", "team_id")
    op.drop_column("assistants", "project_key")

    op.create_table(
        "link_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("installations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )

    op.add_column("teams", sa.Column("slug", sa.String(40), nullable=True))
    op.add_column(
        "teams", sa.Column("last_topic", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("teams", sa.Column("last_file", sa.Integer(), server_default="0", nullable=False))
    taken: set[str] = set()
    for team in bind.execute(sa.text("SELECT id, name FROM teams ORDER BY id")).all():
        slug = numbered(slugify(team.name), taken)
        taken.add(slug)
        bind.execute(
            sa.text("UPDATE teams SET slug = :slug WHERE id = :id"), {"slug": slug, "id": team.id}
        )
    op.alter_column("teams", "slug", nullable=False)
    op.create_unique_constraint("teams_slug_key", "teams", ["slug"])
    op.create_table(
        "former_team_slugs",
        sa.Column("slug", sa.String(40), primary_key=True),
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
        ),
    )

    op.add_column("areas", sa.Column("slug", sa.String(40), nullable=True))
    by_team: dict[int, set[str]] = {}
    for area in bind.execute(sa.text("SELECT id, team_id, name FROM areas ORDER BY id")).all():
        team_taken = by_team.setdefault(area.team_id, set())
        slug = numbered(slugify(area.name, "area"), team_taken)
        team_taken.add(slug)
        bind.execute(
            sa.text("UPDATE areas SET slug = :slug WHERE id = :id"), {"slug": slug, "id": area.id}
        )
    op.alter_column("areas", "slug", nullable=False)
    op.create_unique_constraint("areas_team_id_slug_key", "areas", ["team_id", "slug"])
    op.create_table(
        "former_area_slugs",
        sa.Column(
            "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("slug", sa.String(40), primary_key=True),
        sa.Column(
            "area_id", sa.Integer(), sa.ForeignKey("areas.id", ondelete="CASCADE"), nullable=False
        ),
    )

    op.add_column("topics", sa.Column("number", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE topics SET number = ordered.number
        FROM (
            SELECT id, row_number() OVER (PARTITION BY team_id ORDER BY id) AS number
            FROM topics
        ) AS ordered
        WHERE topics.id = ordered.id
        """
    )
    op.alter_column("topics", "number", nullable=False)
    op.create_unique_constraint("topics_team_id_number_key", "topics", ["team_id", "number"])
    op.execute(
        "UPDATE teams SET last_topic = coalesce("
        "(SELECT max(number) FROM topics WHERE topics.team_id = teams.id), 0)"
    )

    op.add_column(
        "files",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE")),
    )
    op.add_column("files", sa.Column("number", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE files SET team_id = topics.team_id FROM topics WHERE topics.id = files.topic_id"
    )
    op.execute(
        """
        UPDATE files SET number = ordered.number
        FROM (
            SELECT id, row_number() OVER (PARTITION BY team_id ORDER BY id) AS number
            FROM files
        ) AS ordered
        WHERE files.id = ordered.id
        """
    )
    op.alter_column("files", "team_id", nullable=False)
    op.alter_column("files", "number", nullable=False)
    op.create_unique_constraint("files_team_id_number_key", "files", ["team_id", "number"])
    op.execute(
        "UPDATE teams SET last_file = coalesce("
        "(SELECT max(number) FROM files WHERE files.team_id = teams.id), 0)"
    )

    human_part = sa.Enum("without", "with", "words", name="human_part")
    human_part.create(bind, checkfirst=True)
    op.add_column("messages", sa.Column("human_part", human_part, nullable=True))
    op.execute("UPDATE messages SET human_part = 'words' WHERE relayed")


def downgrade() -> None:
    """Revert the migration."""
    bind = op.get_bind()
    op.execute("UPDATE messages SET kind = 'stage' WHERE kind = 'taken'")
    op.drop_column("messages", "human_part")
    op.drop_constraint("files_team_id_number_key", "files", type_="unique")
    op.drop_column("files", "number")
    op.drop_column("files", "team_id")
    op.drop_constraint("topics_team_id_number_key", "topics", type_="unique")
    op.drop_column("topics", "number")
    op.drop_table("former_area_slugs")
    op.drop_constraint("areas_team_id_slug_key", "areas", type_="unique")
    op.drop_column("areas", "slug")
    op.drop_table("former_team_slugs")
    op.drop_constraint("teams_slug_key", "teams", type_="unique")
    for column in ("last_file", "last_topic", "slug"):
        op.drop_column("teams", column)
    op.drop_table("link_requests")

    op.add_column("assistants", sa.Column("project_key", sa.String(64), nullable=True))
    op.add_column("assistants", sa.Column("team_id", sa.Integer(), nullable=True))
    keep = {
        row.project_id: row.id
        for row in bind.execute(
            sa.text(
                "SELECT DISTINCT ON (project_id) project_id, id FROM assistants "
                "ORDER BY project_id, id"
            )
        ).all()
    }
    for row in bind.execute(sa.text("SELECT id, project_id FROM assistants")).all():
        kept = keep[row.project_id]
        if row.id == kept:
            continue
        for table, column in (
            ("messages", "author_assistant_id"),
            ("messages", "to_assistant_id"),
            ("topics", "holder_assistant_id"),
            ("files", "uploaded_by_assistant_id"),
        ):
            bind.execute(
                sa.text(f"UPDATE {table} SET {column} = :kept WHERE {column} = :gone"),
                {"kept": kept, "gone": row.id},
            )
        bind.execute(sa.text("DELETE FROM assistants WHERE id = :id"), {"id": row.id})
    op.execute(
        """
        UPDATE assistants SET project_key = projects.project_key, team_id = projects.team_id,
            name = split_part(assistants.name, ' · ', 1) || ' · ' || projects.name
        FROM projects WHERE projects.id = assistants.project_id
        """
    )
    op.alter_column("assistants", "project_key", nullable=False)
    op.create_foreign_key(
        "assistants_team_id_fkey", "assistants", "teams", ["team_id"], ["id"], ondelete="SET NULL"
    )
    op.drop_constraint("assistants_project_id_session_key_key", "assistants", type_="unique")
    op.create_unique_constraint(
        "assistants_installation_id_project_key_key",
        "assistants",
        ["installation_id", "project_key"],
    )
    op.drop_constraint("assistants_key_key", "assistants", type_="unique")
    for column in ("word", "session_id", "session_key", "project_id", "key"):
        op.drop_column("assistants", column)
    op.alter_column("assistants", "name", type_=sa.String(100))
    op.drop_table("projects")
    op.drop_constraint("installations_key_key", "installations", type_="unique")
    op.drop_column("installations", "key")

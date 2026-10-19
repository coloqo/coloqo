"""image type of files

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19 18:00:00.000000

Files uploaded before decision 0018 get their image type from their content on disk.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import context, op

from coloqo_server.images import SIGNATURE_BYTES, image_type

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration.

    Raises:
        KeyError: The migration was run without the instance's file directory.
        OSError: A file's content cannot be read.
    """
    op.add_column("files", sa.Column("image_type", sa.String(length=20), nullable=True))
    files_dir = Path(context.config.attributes["files_dir"])
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT files.id, topics.team_id FROM files JOIN topics ON topics.id = files.topic_id"
        )
    )
    for file_id, team_id in rows.all():
        path = files_dir / str(team_id) / str(file_id)
        if not path.is_file():
            continue
        with path.open("rb") as content:
            kind = image_type(content.read(SIGNATURE_BYTES))
        if kind is not None:
            connection.execute(
                sa.text("UPDATE files SET image_type = :kind WHERE id = :id"),
                {"kind": kind, "id": file_id},
            )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("files", "image_type")

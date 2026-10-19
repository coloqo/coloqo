"""Non-secret files shared in Topics (decision 0008)."""

import hashlib
import os
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from coloqo_server.api.topics import FileOut, get_topic
from coloqo_server.images import SIGNATURE_BYTES, image_type
from coloqo_server.models import File, Topic
from coloqo_server.security import DB, ActorDep

router = APIRouter(tags=["files"])

CHUNK = 1024 * 1024

FILE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "X-Content-Type-Options": "nosniff",
}
"""Sent with every file: whatever a file holds, a browser never runs it (decision 0018)."""


def _path(files_dir: Path, file: File, team_id: int) -> Path:
    """Return where a file's content is kept.

    Args:
        files_dir: The instance's file directory.
        file: The file.
        team_id: Its Team.
    """
    return files_dir / str(team_id) / str(file.id)


@router.post("/topics/{topic_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    topic_id: int,
    actor: ActorDep,
    db: DB,
    x_file_name: Annotated[str, Header()],
    content_type: Annotated[str, Header()] = "application/octet-stream",
) -> FileOut:
    """Upload a file into a Topic; the request body is the content.

    Attach it to a Message by its id. Files are not secret: everyone in the Team can read
    them (decision 0005 covers secrets).

    Args:
        request: The incoming request with the content as its body.
        topic_id: The Topic.
        actor: The caller.
        db: Database session.
        x_file_name: File name, percent-encoded.
        content_type: Media type of the content.

    Raises:
        HTTPException: 404 when there is no such Topic; 403 when the caller may not write
            there (decision 0020); 410 for a deleted Topic; 422 for an empty name; 413 when
            the file or the Team's storage is over the limit.
        OSError: The file cannot be written.
    """
    settings = request.app.state.settings
    topic = await get_topic(db, topic_id, actor, write=True)
    name = os.path.basename(unquote(x_file_name).replace("\\", "/")).strip()[:255]
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file needs a name")
    used = await _team_usage(db, topic.team_id)
    limit = min(settings.max_file_bytes, settings.team_storage_bytes - used)
    if limit <= 0:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The Team's file storage is full")
    temp_dir = Path(settings.files_dir) / "incoming"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp = temp_dir / f"{os.getpid()}-{id(request)}"
    digest = hashlib.sha256()
    size = 0
    head = b""
    try:
        with temp.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"The file is larger than {limit // (1024 * 1024)} MB allowed",
                    )
                if len(head) < SIGNATURE_BYTES:
                    head += chunk[: SIGNATURE_BYTES - len(head)]
                digest.update(chunk)
                out.write(chunk)
        file = File(
            topic_id=topic.id,
            name=name,
            size=size,
            sha256=digest.hexdigest(),
            content_type=content_type.split(";")[0].strip()[:100] or "application/octet-stream",
            image_type=image_type(head),
            uploaded_by=actor.user.id,
            uploaded_by_assistant_id=actor.assistant.id if actor.assistant else None,
        )
        db.add(file)
        await db.flush()
        target = _path(Path(settings.files_dir), file, topic.team_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.replace(target)
        await db.commit()
    finally:
        temp.unlink(missing_ok=True)
    return FileOut(
        id=file.id,
        name=file.name,
        size=file.size,
        sha256=file.sha256,
        content_type=file.content_type,
        preview=file.image_type is not None and file.size <= settings.preview_max_bytes,
        uploaded_by=actor.user.pseudonym,
        message_number=None,
        created_at=file.created_at,
    )


async def _team_usage(db: DB, team_id: int) -> int:
    """Return the bytes of files a Team keeps.

    Args:
        db: Database session.
        team_id: The Team.
    """
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(File.size), 0))
            .join(Topic, Topic.id == File.topic_id)
            .where(Topic.team_id == team_id)
        )
        or 0
    )


@router.get("/files/{file_id}")
async def download_file(
    request: Request,
    file_id: int,
    actor: ActorDep,
    db: DB,
    download: Annotated[bool, Query()] = False,
) -> FileResponse:
    """Download a file of one of the caller's Teams.

    A raster image recognised at upload is served inline with its own type, so the web can
    show it (decision 0018); any other file is an attachment of an opaque type. Either way
    the browser never renders it as a page.

    Args:
        request: The incoming request.
        file_id: The file.
        actor: The caller.
        db: Database session.
        download: Serve an image as an attachment too, to save it under its name.

    Raises:
        HTTPException: 404 when there is no such file for the caller; 403 for a plugin
            request without an Assistant.
    """
    file = await db.get(File, file_id)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file")
    topic = await get_topic(db, file.topic_id, actor)
    path = _path(Path(request.app.state.settings.files_dir), file, topic.team_id)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The file's content is missing")
    inline = file.image_type is not None and not download
    return FileResponse(
        path,
        media_type=file.image_type if inline else "application/octet-stream",
        filename=file.name,
        headers={"X-Content-SHA256": file.sha256, **FILE_HEADERS},
        content_disposition_type="inline" if inline else "attachment",
    )

"""People's avatars: uploaded or taken from GitHub once, always re-encoded (decision 0019)."""

import asyncio
import io
import warnings
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import aliased

from coloqo_server.models import Identity, Member, User
from coloqo_server.security import DB, AnyActorDep, HumanDep

router = APIRouter(tags=["avatars"])

SIZE = 256
"""Side of the square an avatar is stored as, in pixels."""

MAX_UPLOAD = 10 * 1024 * 1024
"""Largest picture accepted for an avatar, before re-encoding."""

MAX_PIXELS = 25_000_000
"""Largest picture decoded, in pixels: a phone photo fits; a flat 10 MB PNG of a huge size
would take hundreds of megabytes once decoded."""

AVATAR_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "X-Content-Type-Options": "nosniff",
    # The address carries the version, so a new avatar is a new address.
    "Cache-Control": "private, max-age=31536000, immutable",
}


def avatar_url(user: User) -> str | None:
    """Return where a person's avatar is served, or ``None`` when they have none.

    Args:
        user: The person.
    """
    if user.avatar_version is None:
        return None
    return f"/api/avatars/{user.id}?v={user.avatar_version}"


def _path(request: Request, user_id: int) -> Path:
    """Return where an avatar's file is kept.

    Args:
        request: The incoming request, for the instance's file directory.
        user_id: Whose avatar.
    """
    return Path(request.app.state.settings.files_dir) / "avatars" / f"{user_id}.webp"


def square_webp(data: bytes) -> bytes:
    """Re-encode a picture as a centred square WebP; the photo's metadata, GPS too, is dropped.

    Args:
        data: The picture as uploaded or fetched.

    Raises:
        HTTPException: 422 when it is not a picture Pillow can read, or is over 25 megapixels.
    """
    try:
        with warnings.catch_warnings():
            # Pillow only warns between its limit and twice it; here that is a refusal too.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            return _encode(data)
    except Exception as error:
        # A decoder fails in many ways on a crafted file; each of them is "not a picture".
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "This is not a picture that can be an avatar"
        ) from error


def _encode(data: bytes) -> bytes:
    """Decode, turn upright, crop and encode a picture; ``square_webp`` guards it.

    Args:
        data: The picture.

    Raises:
        PIL.Image.DecompressionBombWarning: The picture is over ``MAX_PIXELS``, as an error.
        PIL.UnidentifiedImageError: It is not a picture.
        OSError: It is broken.
    """
    with Image.open(io.BytesIO(data)) as picture:
        if picture.width * picture.height > MAX_PIXELS:
            raise Image.DecompressionBombWarning("The picture is too large")
        upright = ImageOps.exif_transpose(picture)
        has_alpha = upright.mode in ("RGBA", "LA", "PA") or "transparency" in upright.info
        square = ImageOps.fit(
            upright.convert("RGBA" if has_alpha else "RGB"), (SIZE, SIZE), Image.Resampling.LANCZOS
        )
        out = io.BytesIO()
        square.save(out, "WEBP", quality=85)
        return out.getvalue()


async def _store(request: Request, db: DB, user: User, data: bytes) -> None:
    """Re-encode a picture, keep it as the person's avatar and bump its version.

    Args:
        request: The incoming request.
        db: Database session.
        user: The person.
        data: The picture.

    Raises:
        HTTPException: 422 when it is not a usable picture.
        OSError: The file cannot be written.
    """
    encoded = await asyncio.to_thread(square_webp, data)
    path = _path(request, user.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".part")
    temp.write_bytes(encoded)
    temp.replace(path)
    user.avatar_version = (user.avatar_version or 0) + 1
    db.add(user)
    await db.commit()


@router.put("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def upload_avatar(request: Request, actor: HumanDep, db: DB) -> Response:
    """Set the person's avatar from an uploaded picture; the request body is the picture.

    Args:
        request: The incoming request.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 413 over 10 MB; 422 when it is not a usable picture.
        OSError: The file cannot be written.
    """
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_UPLOAD:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The picture is over 10 MB")
    await _store(request, db, actor.user, bytes(data))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def fetch_github_avatar(url: str) -> bytes:
    """Download an avatar from GitHub by the server, so the browser never calls GitHub.

    Args:
        url: The avatar's address.

    Raises:
        HTTPException: 502 when GitHub does not give a picture.
    """
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            response = await client.get(url)
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitHub did not answer") from error
    if response.status_code != 200 or len(response.content) > MAX_UPLOAD:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitHub did not give an avatar")
    return response.content


@router.post("/me/avatar/github", status_code=status.HTTP_204_NO_CONTENT)
async def avatar_from_github(request: Request, actor: HumanDep, db: DB) -> Response:
    """Take the person's GitHub avatar once, by the GitHub id the server keeps (decision 0014).

    Args:
        request: The incoming request.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 409 without a GitHub login; 502 when GitHub does not give a picture;
            422 when it is not a usable picture.
        OSError: The file cannot be written.
    """
    subject = await db.scalar(
        select(Identity.subject).where(
            Identity.user_id == actor.user.id, Identity.provider == "github"
        )
    )
    if subject is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This account has no GitHub login")
    url = request.app.state.settings.github_avatar_url.format(id=subject)
    await _store(request, db, actor.user, await fetch_github_avatar(url))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def remove_avatar(request: Request, actor: HumanDep, db: DB) -> Response:
    """Remove the person's avatar; their initials are shown again.

    Args:
        request: The incoming request.
        actor: The logged-in human.
        db: Database session.
    """
    _path(request, actor.user.id).unlink(missing_ok=True)
    actor.user.avatar_version = None
    db.add(actor.user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/avatars/{user_id}")
async def get_avatar(
    request: Request,
    user_id: int,
    actor: AnyActorDep,
    db: DB,
    v: int | None = Query(default=None),
) -> FileResponse:
    """Serve an avatar to its person and to the people who share a Team with them.

    Args:
        request: The incoming request.
        user_id: Whose avatar.
        actor: The caller.
        db: Database session.
        v: The avatar's version; only makes the address change with it.

    Raises:
        HTTPException: 404 when there is no avatar, or the caller shares no Team with them.
    """
    if user_id != actor.user.id:
        theirs, mine = aliased(Member), aliased(Member)
        shared = await db.scalar(
            select(theirs.team_id)
            .join(mine, mine.team_id == theirs.team_id)
            .where(theirs.user_id == user_id, mine.user_id == actor.user.id)
            .limit(1)
        )
        if shared is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such avatar")
    path = _path(request, user_id)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such avatar")
    return FileResponse(path, media_type="image/webp", headers=AVATAR_HEADERS)

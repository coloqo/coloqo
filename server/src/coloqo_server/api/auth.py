"""Logging in: humans through providers, the plugin by a confirmed code (decision 0003)."""

import html
import re
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from coloqo_server.models import DeviceLogin, Identity, Installation, User, WebSession
from coloqo_server.providers import LoginProvider, ProviderError
from coloqo_server.security import (
    DB,
    SESSION_COOKIE,
    AnyActorDep,
    AnyHumanDep,
    new_token,
    now,
    token_hash,
)

router = APIRouter(tags=["auth"])

SESSION_DAYS = 30
STATE_COOKIE = "coloqo_oauth_state"
DEVICE_MINUTES = 10
PSEUDONYM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,31}")
USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"


class Me(BaseModel):
    """The caller.

    Attributes:
        id: User id.
        pseudonym: The chosen name, ``None`` until chosen.
        via: ``web`` for the browser, ``plugin`` for an installation token.
        assistant: Name of the calling Assistant, if the plugin named one.
        providers: Login providers the instance offers.
    """

    id: int
    pseudonym: str | None
    via: str
    assistant: str | None = None
    providers: list[str]


class PseudonymIn(BaseModel):
    """A chosen name.

    Attributes:
        pseudonym: 2-32 latin letters, digits, ``_``, ``.``, ``-``; starts with a letter or
            digit. Seen by the Team and used to address the person.
    """

    pseudonym: str = Field(min_length=2, max_length=32)


class DevLoginIn(BaseModel):
    """Development login by name.

    Attributes:
        pseudonym: Whom to log in as; the User is created if needed.
    """

    pseudonym: str


class DeviceStartIn(BaseModel):
    """A plugin starting login.

    Attributes:
        name: Name of the installation, e.g. the computer's host name.
    """

    name: str = Field(min_length=1, max_length=100)


class DeviceStartOut(BaseModel):
    """What the plugin shows the human and polls with.

    Attributes:
        device_code: Secret the plugin polls with.
        user_code: Short code the human confirms.
        verification_uri: Page where the code is confirmed.
        verification_uri_complete: The same page with the code filled in.
        interval: Seconds between polls.
        expires_in: Seconds until the code expires.
    """

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    interval: int
    expires_in: int


class DeviceTokenIn(BaseModel):
    """A plugin polling for its token.

    Attributes:
        device_code: The secret from ``DeviceStartOut``.
    """

    device_code: str


class DeviceTokenOut(BaseModel):
    """The installation token, handed out once.

    Attributes:
        token: The installation token.
        pseudonym: Whose installation it is.
    """

    token: str
    pseudonym: str | None


class DeviceLoginOut(BaseModel):
    """A pending plugin login as the human sees it.

    Attributes:
        user_code: The code.
        name: Name of the installation that asks.
        state: ``pending``, ``approved``, ``denied`` or ``expired``.
    """

    user_code: str
    name: str
    state: str


class InstallationOut(BaseModel):
    """An installation of the plugin.

    Attributes:
        id: Identifier.
        name: Name given at login.
        created_at: When login was confirmed.
        last_seen_at: The last request.
        revoked: The token no longer works.
    """

    id: int
    name: str
    created_at: str
    last_seen_at: str | None
    revoked: bool


def _providers(request: Request) -> dict[str, LoginProvider]:
    """Return the instance's login providers by name.

    Args:
        request: The incoming request.
    """
    return request.app.state.providers


def _callback_uri(request: Request, provider: str) -> str:
    """Return the callback address registered at the provider.

    Args:
        request: The incoming request.
        provider: Provider name.
    """
    return f"{request.app.state.settings.public_url}/api/auth/{provider}/callback"


def _safe_next(next_path: str | None) -> str:
    """Keep a return path on this site.

    Args:
        next_path: Path requested by the web interface.
    """
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


async def _start_session(db: DB, user: User) -> str:
    """Create a web session and return its cookie value.

    Args:
        db: Database session.
        user: Who logs in.
    """
    token = new_token()
    db.add(
        WebSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=now() + timedelta(days=SESSION_DAYS),
        )
    )
    await db.commit()
    return token


def _set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie (decision 0013: ``__Host-``, Secure, Strict).

    Args:
        response: The response that logs in.
        token: Cookie value.
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _same_site_redirect(target: str) -> HTMLResponse:
    """Go to ``target`` by a page of this site.

    A redirect straight from the provider's callback is a cross-site navigation, and the
    browser would not send the new ``SameSite=Strict`` cookie with it; a refresh from our own
    page is same-site.

    Args:
        target: Path on this site.
    """
    url = html.escape(target, quote=True)
    return HTMLResponse(
        f'<!doctype html><meta http-equiv="refresh" content="0;url={url}">'
        f'<title>Coloqo</title><a href="{url}">Coloqo</a>'
    )


@router.get("/auth/{provider}/start")
async def login_start(
    request: Request, provider: str, next: Annotated[str | None, Query()] = None
) -> RedirectResponse:
    """Send the browser to the provider's login page.

    Args:
        request: The incoming request.
        provider: Provider name, ``github``.
        next: Path to return to after login.

    Raises:
        HTTPException: 404 for a provider the instance does not offer.
    """
    login_provider = _providers(request).get(provider)
    if login_provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown login provider")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(
        login_provider.authorize_url(state, _callback_uri(request, provider)), status_code=302
    )
    # Lax, not Strict: the provider's callback is a cross-site navigation that must carry it.
    response.set_cookie(
        STATE_COOKIE,
        f"{state}:{_safe_next(next)}",
        max_age=600,
        path="/api/auth",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/auth/{provider}/callback")
async def login_callback(
    request: Request,
    provider: str,
    db: DB,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> HTMLResponse:
    """Finish provider login: find or create the User and start a web session.

    Args:
        request: The incoming request.
        provider: Provider name.
        db: Database session.
        code: Code from the provider.
        state: The value sent in ``login_start``.

    Raises:
        HTTPException: 404 for an unknown provider; 400 when the state does not match;
            502 when the provider refuses the code.
    """
    login_provider = _providers(request).get(provider)
    if login_provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown login provider")
    expected_state, _, next_path = request.cookies.get(STATE_COOKIE, "").partition(":")
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Login expired; start again")
    try:
        subject = await login_provider.subject(code, _callback_uri(request, provider))
    except ProviderError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    identity = await db.scalar(
        select(Identity).where(Identity.provider == provider, Identity.subject == subject)
    )
    if identity is None:
        user = User()
        db.add(user)
        await db.flush()
        db.add(Identity(user_id=user.id, provider=provider, subject=subject))
    else:
        user = await db.get(User, identity.user_id)
    assert user is not None
    response = _same_site_redirect(_safe_next(next_path))
    _set_session_cookie(response, await _start_session(db, user))
    response.delete_cookie(STATE_COOKIE, path="/api/auth")
    return response


@router.post("/auth/dev", status_code=status.HTTP_204_NO_CONTENT)
async def dev_login(request: Request, body: DevLoginIn, db: DB) -> Response:
    """Log in by name, without a provider; only when the instance allows it.

    Args:
        request: The incoming request.
        body: Whom to log in as.
        db: Database session.

    Raises:
        HTTPException: 404 when development login is off.
    """
    if not request.app.state.settings.dev_login:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    user = await db.scalar(select(User).where(User.pseudonym == body.pseudonym))
    if user is None:
        user = User(pseudonym=body.pseudonym)
        db.add(user)
        await db.flush()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_session_cookie(response, await _start_session(db, user))
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, actor: AnyHumanDep, db: DB) -> Response:
    """End the web session.

    Args:
        request: The incoming request.
        actor: The logged-in human.
        db: Database session.
    """
    session = await db.scalar(
        select(WebSession).where(
            WebSession.token_hash == token_hash(request.cookies.get(SESSION_COOKIE, ""))
        )
    )
    if session is not None:
        await db.delete(session)
        await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True)
    return response


@router.get("/me")
async def me(request: Request, actor: AnyActorDep) -> Me:
    """Return who is calling.

    Args:
        request: The incoming request.
        actor: The caller.
    """
    return Me(
        id=actor.user.id,
        pseudonym=actor.user.pseudonym,
        via="web" if actor.is_human else "plugin",
        assistant=actor.assistant.name if actor.assistant else None,
        providers=sorted(_providers(request)),
    )


@router.get("/auth/providers")
async def providers(request: Request) -> list[str]:
    """Return the login providers the instance offers, for the login page.

    Args:
        request: The incoming request.
    """
    names = sorted(_providers(request))
    return [*names, "dev"] if request.app.state.settings.dev_login else names


@router.put("/me/pseudonym")
async def set_pseudonym(request: Request, body: PseudonymIn, actor: AnyHumanDep, db: DB) -> Me:
    """Choose or change the name the Team sees.

    Args:
        request: The incoming request.
        body: The new name.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 422 for a name of the wrong form; 409 when it is taken.
    """
    if not PSEUDONYM.fullmatch(body.pseudonym):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Use 2-32 latin letters, digits, '_', '.', '-', starting with a letter or digit",
        )
    taken = await db.scalar(
        select(User.id).where(
            func.lower(User.pseudonym) == body.pseudonym.lower(), User.id != actor.user.id
        )
    )
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This name is taken")
    actor.user.pseudonym = body.pseudonym
    db.add(actor.user)
    try:
        await db.commit()
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "This name is taken") from error
    return await me(request, actor)


@router.post("/device/start")
async def device_start(request: Request, body: DeviceStartIn, db: DB) -> DeviceStartOut:
    """Start a plugin login: the human confirms the code in the browser.

    Args:
        request: The incoming request.
        body: Name of the installation.
        db: Database session.
    """
    device_code = new_token()
    user_code = "-".join(
        "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(4)) for _ in range(2)
    )
    db.add(
        DeviceLogin(
            device_code_hash=token_hash(device_code),
            user_code=user_code,
            name=body.name,
            expires_at=now() + timedelta(minutes=DEVICE_MINUTES),
        )
    )
    await db.commit()
    page = f"{request.app.state.settings.public_url}/device"
    return DeviceStartOut(
        device_code=device_code,
        user_code=user_code,
        verification_uri=page,
        verification_uri_complete=f"{page}?code={user_code}",
        interval=3,
        expires_in=DEVICE_MINUTES * 60,
    )


@router.post("/device/token")
async def device_token(body: DeviceTokenIn, db: DB) -> DeviceTokenOut:
    """Collect the installation token once the human has confirmed the code.

    Args:
        body: The plugin's device code.
        db: Database session.

    Raises:
        HTTPException: 400 with ``authorization_pending``, ``access_denied`` or
            ``expired_token`` while there is no token to hand out.
    """
    login = await db.scalar(
        select(DeviceLogin).where(DeviceLogin.device_code_hash == token_hash(body.device_code))
    )
    if login is None or login.expires_at < now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "expired_token")
    if login.denied:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "access_denied")
    if login.token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "authorization_pending")
    token = login.token
    user = await db.get(User, login.user_id)
    await db.delete(login)
    await db.commit()
    return DeviceTokenOut(token=token, pseudonym=user.pseudonym if user else None)


async def _device_login(db: DB, user_code: str) -> DeviceLogin:
    """Find a pending login by the code the human typed.

    Args:
        db: Database session.
        user_code: The code, any case, with or without the dash.

    Raises:
        HTTPException: 404 when there is no such code.
    """
    code = user_code.strip().upper().replace("-", "")
    code = f"{code[:4]}-{code[4:]}"
    login = await db.scalar(select(DeviceLogin).where(DeviceLogin.user_code == code))
    if login is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such code; start login again")
    return login


def _device_state(login: DeviceLogin) -> str:
    """Return the state of a plugin login for the human.

    Args:
        login: The login.
    """
    if login.denied:
        return "denied"
    if login.token is not None:
        return "approved"
    return "expired" if login.expires_at < now() else "pending"


@router.get("/device/{user_code}")
async def device_show(user_code: str, actor: AnyHumanDep, db: DB) -> DeviceLoginOut:
    """Show a plugin login to the human who is about to confirm it.

    Args:
        user_code: The code.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such code.
    """
    login = await _device_login(db, user_code)
    return DeviceLoginOut(user_code=login.user_code, name=login.name, state=_device_state(login))


@router.post("/device/{user_code}/approve")
async def device_approve(user_code: str, actor: AnyHumanDep, db: DB) -> DeviceLoginOut:
    """Confirm a plugin login: create the installation and its token.

    Args:
        user_code: The code.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such code; 409 when it is no longer pending.
    """
    login = await _device_login(db, user_code)
    if _device_state(login) != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This login is {_device_state(login)}")
    token = new_token()
    installation = Installation(
        user_id=actor.user.id, name=login.name, token_hash=token_hash(token)
    )
    db.add(installation)
    await db.flush()
    login.user_id = actor.user.id
    login.installation_id = installation.id
    login.token = token
    await db.commit()
    return DeviceLoginOut(user_code=login.user_code, name=login.name, state="approved")


@router.post("/device/{user_code}/deny")
async def device_deny(user_code: str, actor: AnyHumanDep, db: DB) -> DeviceLoginOut:
    """Refuse a plugin login.

    Args:
        user_code: The code.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when there is no such code.
    """
    login = await _device_login(db, user_code)
    login.denied = True
    await db.commit()
    return DeviceLoginOut(user_code=login.user_code, name=login.name, state="denied")


@router.get("/installations")
async def installations(actor: AnyHumanDep, db: DB) -> list[InstallationOut]:
    """List the human's plugin installations (decision 0003).

    Args:
        actor: The logged-in human.
        db: Database session.
    """
    rows = await db.scalars(
        select(Installation)
        .where(Installation.user_id == actor.user.id)
        .order_by(Installation.created_at.desc())
    )
    return [
        InstallationOut(
            id=row.id,
            name=row.name,
            created_at=row.created_at.isoformat(),
            last_seen_at=row.last_seen_at.isoformat() if row.last_seen_at else None,
            revoked=row.revoked_at is not None,
        )
        for row in rows
    ]


@router.delete("/installations/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_installation(installation_id: int, actor: AnyHumanDep, db: DB) -> Response:
    """Revoke an installation: its token stops working.

    Args:
        installation_id: The installation.
        actor: The logged-in human.
        db: Database session.

    Raises:
        HTTPException: 404 when it is not the human's installation.
    """
    installation = await db.get(Installation, installation_id)
    if installation is None or installation.user_id != actor.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such installation")
    installation.revoked_at = installation.revoked_at or now()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

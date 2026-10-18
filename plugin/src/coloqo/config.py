"""Where the plugin talks to and what it remembers between runs."""

import json
import os
import sys
from pathlib import Path

DEFAULT_URL = "https://app.coloqo.team"


def server_url() -> str:
    """Return the Coloqo address: ``COLOQO_URL`` or the cloud instance."""
    return os.environ.get("COLOQO_URL", DEFAULT_URL).rstrip("/")


def config_dir() -> Path:
    """Return the per-user configuration directory of the plugin.

    ``%APPDATA%\\coloqo`` on Windows, ``~/Library/Application Support/coloqo`` on macOS,
    ``$XDG_CONFIG_HOME/coloqo`` (``~/.config/coloqo``) elsewhere.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "coloqo"


def _credentials_path() -> Path:
    """Return the file with installation tokens, one per server address."""
    return config_dir() / "credentials.json"


def _read_all() -> dict[str, dict[str, str]]:
    """Return all saved credentials; empty when there are none or the file is broken."""
    try:
        return json.loads(_credentials_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_token(url: str | None = None) -> str | None:
    """Return the installation token for a server, if this computer is logged in.

    Args:
        url: Server address; ``server_url()`` when omitted.
    """
    return _read_all().get(url or server_url(), {}).get("token")


def save_token(token: str, pseudonym: str | None, url: str | None = None) -> Path:
    """Remember the installation token in a file only the user can read (decision 0003).

    Args:
        token: The installation token.
        pseudonym: Whose installation it is, for messages.
        url: Server address; ``server_url()`` when omitted.

    Raises:
        OSError: The file cannot be written.
    """
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_all()
    data[url or server_url()] = {"token": token, "pseudonym": pseudonym or ""}
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2)
    os.replace(temp, path)
    return path


def forget_token(url: str | None = None) -> bool:
    """Drop the saved token for a server.

    Args:
        url: Server address; ``server_url()`` when omitted.

    Raises:
        OSError: The file cannot be written.
    """
    data = _read_all()
    if data.pop(url or server_url(), None) is None:
        return False
    path = _credentials_path()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2)
    return True

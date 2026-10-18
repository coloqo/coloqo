"""Serving the built web interface."""

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SinglePageApp(StaticFiles):
    """Static files of a single-page app: an unknown path gets ``index.html``.

    The web interface routes on the client, so ``/teams/acme`` has no file of its own
    and is answered with the app's entry page. Mounted at ``/``, it also receives the
    ``/api`` paths no API route matched; those stay 404.
    """

    def __init__(self, directory: str) -> None:
        """Serve the given directory.

        Args:
            directory: The built web interface, with ``index.html`` at its root.

        Raises:
            RuntimeError: The directory does not exist (raised by ``StaticFiles``).
        """
        super().__init__(directory=directory, html=True, check_dir=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Return the file at ``path``, or ``index.html`` when there is none.

        Args:
            path: Path of the requested file, relative to the directory.
            scope: ASGI scope of the request.

        Raises:
            HTTPException: 404 for a missing file under ``assets/`` or ``api/`` — a stale
                hashed asset or an unknown API path must fail loudly, not turn into
                HTML; 405 for a method other than GET and HEAD (raised by
                ``StaticFiles``).
        """
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path.startswith(("assets/", "api/")):
                raise
            return await super().get_response("index.html", scope)

# Coloqo

[RU](README.ru.md)

When every member of a team works with an AI assistant, the assistants need a way to work with
each other: ask a colleague's assistant for a script or an explanation, discuss a decision before code
is written, call a human in when the decision is theirs, and leave the outcome where the team
keeps its records — in the merge request and the issue.

Coloqo is a service for that coordination.

**Status:** implementation has started: server and web skeleton, the welcome page.

## Development

The server needs Python 3.14 and [uv](https://docs.astral.sh/uv/); the web needs Node 24; the
plugin supports Python 3.12 and later.

```sh
cd server && uv sync && uv run uvicorn coloqo_server.app:create_app --factory --reload
cd web && npm install && npm run dev   # http://localhost:5173, /api goes to :8000
```

Checks: `uv run pytest`, `uv run ruff check` in `server/` and `plugin/`; `npm run lint`,
`npm run build` in `web/`. The image is built from the root `Dockerfile`; deployment is
described in [deploy/README.md](deploy/README.md).

## License

The server and the web interface are licensed under [AGPL-3.0](LICENSE); the plugin
([`plugin/`](plugin/), [`coloqo` on PyPI](https://pypi.org/project/coloqo/)) under
[Apache-2.0](plugin/LICENSE). The core of Coloqo stays open source under these licenses.
Contributions are accepted under a Contributor License Agreement — see
[CONTRIBUTING.md](CONTRIBUTING.md).

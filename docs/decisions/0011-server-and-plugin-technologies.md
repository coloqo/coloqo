# 0011. Server and plugin technologies

**Date:** 2026-10-17 · **Question:** A9, `docs/architecture/architecture.md`

**Refined by decision 0027** (2026-10-20): the plugin keeps itself up to date.

**Refined 2026-10-18:** the plugin package on PyPI is `coloqo`, not `coloqo-plugin`: `uvx coloqo@<version> mcp`
is shorter and matches the command name (author). The plugin license is Apache-2.0 (M4).

## Decision

- **Server — Python 3.14**, FastAPI, SQLAlchemy 2 with Alembic, psycopg 3; SSE via Starlette.
  Modules (seam 4, decision 0009) are separate Python packages loaded through entry points; the
  cloud module is a package from a private repository. Delivery — a container image.
- **Plugin — Python, `requires-python >= 3.12`**, tests on 3.12, 3.13 and 3.14. The core is one
  command `coloqo` with subcommands `mcp`, `hook <event>`, `watch`, `login`.
- **The adapter for an agent is configuration, not code.**
  - Claude Code — a plugin: `.mcp.json`, hooks, monitor and skill call
    `uvx coloqo-plugin@<version> …`.
  - Later: Qwen Code, Gemini CLI, Codex CLI, Continue CLI — their settings files with the same
    commands; OpenCode and Cline — a short JS plugin that calls `coloqo`.
  - The boundary between the core and the adapters is a command with JSON in and out; the core
    can be rewritten in another language without touching the adapters.
- **The per-prompt hook is light.** It does not load cryptography: it asks `coloqo watch` on
  `127.0.0.1`, and without the watch — the cloud. Measure the per-prompt latency on the
  prototype.
- **Plugin libraries:** MCP — the official Python SDK `mcp`; cryptography — `cryptography`
  (X25519, Ed25519, HKDF); file encryption — an established scheme, candidate age via `pyrage`
  (final choice at implementation, decision 0005); OS keychain — `keyring`; HTTP and SSE —
  `httpx`; SSH key signing — the stock `ssh-keygen`.
- **Distribution in the first version:** the plugin catalog is a file in the Coloqo repository on
  GitHub, the package is on PyPI, the version is pinned in `plugin.json`, the server announces a
  new version (decision 0002).
- **One repository:** `server/`, `web/`, `plugin/`, `protocol/` (OpenAPI). Server and web —
  AGPL-3.0, plugin — a permissive license (MIT or Apache-2.0 — when the repository is created).

## Why

- Server: the author's main stack; FastAPI builds OpenAPI from code, so the API description does
  not drift from the implementation. 3.14 — at the author's word (2026-10-17).
- Plugin in Python: `uv` picks the package for the platform and downloads Python itself if no
  suitable one is found. A Claude Code plugin cannot distribute a single Go executable: plugins
  have no selection of a file by OS and architecture, so we would have to pick the build
  ourselves; plus a second language.
- Lower bound 3.12: inside a company network Python downloads are blocked and `uv` takes the
  system one; 3.11 loses security support in October 2027, 3.12 in October 2028, and 3.12 is the
  default in Ubuntu 24.04 LTS (author, 2026-10-17).
- Through one MCP only the tools carry over to other agents; hooks in Qwen Code, Gemini CLI,
  Codex CLI and Continue CLI work almost like Claude Code's, OpenCode and Cline have JS plugins,
  and each has its own analogue of the monitor. The portable basis of delivery is the reminder
  through the input hook (decision 0006); the monitor is an improvement where it exists.

## Sources

- Claude Code documentation, checked 2026-10-17: the `bin/` directory and the variables
  `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`; plugin sources (`github`, `url`, `npm`,
  `archive`), a catalog at any HTTPS address with `marketplace.json`; hooks: the `shell` field,
  the exec form with `args` requires a real `.exe` on Windows, HTTP hooks, the UserPromptSubmit
  limit of 30 s; auto-update of third-party catalogs is off by default.
- `uv 0.11.17` help: "By default, uv will download Python if a version cannot be found".
- Documentation of Qwen Code, Gemini CLI, Codex CLI, OpenCode, Cline, source code of Continue
  CLI — checked 2026-10-17.

# Coloqo

[EN](README.md)

Когда у каждого в команде есть ИИ-ассистент, ассистентам нужен способ работать друг с другом:
попросить у ассистента коллеги скрипт или пояснение, обсудить решение до того, как написан код,
позвать человека, когда решение за ним, и оставить итог там, где команда ведёт свои записи, —
в МР и в задаче.

Coloqo — сервис для такой координации.

**Состояние:** начало реализации: каркас сервера и веба, главная страница.

## Разработка

Сервер — Python 3.14 и [uv](https://docs.astral.sh/uv/), веб — Node 24, плагин — Python 3.12 и
новее.

```sh
cd server && uv sync && uv run uvicorn coloqo_server.app:create_app --factory --reload
cd web && npm install && npm run dev   # http://localhost:5173, /api идёт на :8000
```

Проверки: `uv run pytest`, `uv run ruff check` в `server/` и `plugin/`; `npm run lint`,
`npm run build` в `web/`. Образ — `Dockerfile` в корне; развёртывание —
[deploy/README.md](deploy/README.md) (на английском).

## Лицензия

Сервер и веб — [AGPL-3.0](LICENSE), плагин ([`plugin/`](plugin/),
[`coloqo` на PyPI](https://pypi.org/project/coloqo/)) — [Apache-2.0](plugin/LICENSE). Ядро
Coloqo остаётся открытым под этими лицензиями. Вклады принимаются по соглашению с участником
(CLA) — см. [CONTRIBUTING.md](CONTRIBUTING.md).

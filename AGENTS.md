# BangStats Agent Guide

This guide is for models and automation agents working in this repository.

## Architecture
- Server: FastAPI application in [server/bangstats_server](server/bangstats_server)
- CLI: terminal client in [clients/cli/bangstats_cli](clients/cli/bangstats_cli)
- Web UI: React app in [clients/webui/src](clients/webui/src)
- Rule: clients must access server features over HTTP only

## Canonical Runtime
- API default target: http://127.0.0.1:8010
- Server start: `uv run bangstats server --host 127.0.0.1 --port 8010`
- CLI start: `uv run bangstats client --server-url http://127.0.0.1:8010`
- Web UI start: from [clients/webui](clients/webui), run `npm run dev`
- One-command stack: `uv run python scripts/dev_stack.py`

## Primary Code Surfaces
- API routes: [server/bangstats_server/api/routers](server/bangstats_server/api/routers)
- Schemas: [server/bangstats_server/api/schemas](server/bangstats_server/api/schemas)
- Server config: [server/bangstats_server/core/config.py](server/bangstats_server/core/config.py)
- CLI entrypoint: [clients/cli/bangstats_cli/dispatcher.py](clients/cli/bangstats_cli/dispatcher.py)
- Web API adapter: [clients/webui/src/api.ts](clients/webui/src/api.ts)

## Guardrails
- Keep CLI and Web UI user-visible functionality in parity.
- Keep [AGENTS.md](AGENTS.md) authoritative for repo-wide behavior.
- Use `uv` commands for Python workflows.
- Do not rely on manual virtualenv activation in runbooks.

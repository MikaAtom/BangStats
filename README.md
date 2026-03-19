# BangStats

Self-hosted Bang Dream stats stack with:
- FastAPI server (`bangstats_server`)
- CLI client (`bangstats_cli`)
- React web UI (`clients/webui`)

Ukrainian README: [README_uk.md](README_uk.md)

## What it does
- syncs songs, bands, and events from Bestdori
- scans screenshots with OCR/LLM adapters (Gemini currently wired)
- validates extracted gameplay data
- stores scan outputs in cache and app data in SQLite

## Setup
1. Install `uv`:
   - `brew install uv` (macOS) or see [uv docs](https://docs.astral.sh/uv/)
2. Sync workspace dependencies:
   - `uv sync --dev`
3. Configure environment:
   - Copy `.env.example` to `.env`
   - Set `GOOGLE_API_KEY` (required for scanning features)

## Run
Start server:
- `uv run bangstats server`

Start CLI client (in another terminal):
- `uv run bangstats client`

Start web UI (in another terminal):
- `cd clients/webui`
- `npm install`
- `npm run dev`

You can also run the legacy direct client script:
- `uv run bangstats-client`

### Common command examples
- Server custom host/port:
  - `uv run bangstats server --host 127.0.0.1 --port 8000`
- Server reload mode:
  - `uv run bangstats server --reload`
- Client with prefilled login defaults:
  - `uv run bangstats client --username MikaAtom --game-id 1234567 --server en`
- Client fast init (skip sync + exit):
  - `uv run bangstats client --skip-sync --exit-after-init`

## CLI flow
1. Login or register
2. Optional DB sync job
3. Use dashboard actions:
   - scan screenshots
   - import legacy JSON scans
   - fix scan errors
   - view stats
   - update user settings
   - view sync job history

## Flush parameters
Server startup flush flags:
- `uv run bangstats server --flush-remote-cache`
- `uv run bangstats server --flush-scan-cache --flush-db`
- `uv run bangstats server --flush-all`

Client-triggered admin flush flags:
- `uv run bangstats client --flush-remote-cache`
- `uv run bangstats client --flush-scan-cache --flush-db`
- `uv run bangstats client --flush-all`

Flush operations never hard-delete files. They move data into:
- `storage/backups/<ISO-timestamp>/...`

## Project structure
```text
server/
  bangstats_server/        # FastAPI app + core logic + DB layer

clients/
  cli/
    bangstats_cli/         # CLI client + API client + cache + dispatcher
  webui/                  # React SPA for browser-based workflows

tests/                     # test suite
```

## Where to add new code
- server API/router changes -> `server/bangstats_server/api/`
- server business/data logic -> `server/bangstats_server/core/`
- client UX/menus/arg parsing -> `clients/cli/bangstats_cli/`
- client HTTP integration -> `clients/cli/bangstats_cli/api_client.py`
- client local cache behavior -> `clients/cli/bangstats_cli/cache.py`
- new tests -> `tests/`

## Notes
- This is a pet project: structure is intentionally lightweight.
- Keep boundaries strict: client talks to server via HTTP only.

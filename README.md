# BangStats

CLI tool for scanning BanG Dream! Girls Band Party result screenshots and organizing gameplay data.

Ukrainian README: [README_uk.md](README_uk.md)

## What it does
- syncs songs, bands, and events from Bestdori
- scans screenshots with OCR/LLM adapters (Gemini currently wired)
- validates extracted gameplay data
- stores scan outputs in cache and app data in SQLite

## Setup
1. Install `uv`:
   - `brew install uv` (macOS) or see [uv docs](https://docs.astral.sh/uv/)
2. Sync dependencies:
   - `uv sync --dev`
3. Configure environment (optional but recommended):
   - Copy `.env.example` to `.env` and set `GOOGLE_API_KEY` (required for scanning).
   - Or set `GOOGLE_API_KEY` in your shell.
4. Run:
   - `uv run bangstats`

Optional (global command):
- Install as a uv tool once: `uv tool install --editable .`
- Then run directly: `bangstats`

## Current CLI flow
1. Login/create user profile
2. Sync remote reference data
3. Use dashboard actions:
   - Scan screenshots
   - View your stats (placeholder)
   - Update database
   - Update user settings

## Dev/testing CLI parameters
- Fast startup:
  - `uv run bangstats --username MikaAtom --game-id 1234567 --skip-sync --exit-after-init`
- Pre-fill user creation defaults:
  - `uv run bangstats --username MikaAtom --game-id 1234567 --server en --screenshots-path "/path/to/screenshots"`
- Flush specific data targets (no confirmation prompt):
  - `uv run bangstats --flush-remote-cache`
  - `uv run bangstats --flush-scan-cache --flush-db`
- Flush everything:
  - `uv run bangstats --flush-all`

Flush operations never hard-delete files. They move data into:
- `bangstats/storage/backups/<ISO-timestamp>/...`

## Project structure
```text
bangstats/
  cli/                     # CLI entrypoint + interactive menus
  services/
    scanning/              # scan + validation pipeline
    data/                  # entity-focused business services
  adapters/
    ocr/                   # OCR integrations and prompt templates
    bestdori.py            # Bestdori API adapter
  database/                # db engine, models, repositories
  config/                  # defaults and config loading
  utils/                   # shared utility modules

scripts/                   # project scripts / data transformers
tests/                     # test suite
```

## Where to add new code
- new OCR provider -> `bangstats/adapters/ocr/`
- new OCR prompt -> `bangstats/adapters/ocr/prompts/`
- new external API adapter -> `bangstats/adapters/`
- new scan pipeline logic -> `bangstats/services/scanning/`
- new entity business logic -> `bangstats/services/data/`
- new CLI behavior -> `bangstats/cli/`
- new DB model/repository logic -> `bangstats/database/`

## Notes
- This is a pet project: structure is intentionally lightweight.
- Keep dependencies directional: `cli -> services -> (database, adapters)`.

# BangStats Agent Notes

## Product parity
- The CLI and Web UI must stay 1 to 1 in user-visible functionality.
- Any feature added to the CLI must also be added to the Web UI.
- Any feature added to the Web UI must also be available from the CLI, unless the feature is strictly visual presentation on top of existing data.
- If parity is temporarily broken during implementation, restore it before considering the work complete.

## Architecture boundary
- Clients must talk to the server over HTTP only.
- Do not import server core modules directly into client applications.
- Prefer additive API changes when the clients need shared capabilities.

## Web UI expectations
- The web app should cover the full operational surface of the CLI.
- Visual additions such as screenshot viewers, charts, and calendars are allowed on top of parity, but they must not replace existing CLI workflows.

## Python tooling
- Use `uv` for Python execution, tests, and tooling commands (for example, `uv run pytest -q`).
- Do not rely on manual `.venv` activation in agent instructions or runbooks.

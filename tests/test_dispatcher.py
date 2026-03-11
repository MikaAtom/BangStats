import types

import pytest

from bangstats_cli.dispatcher import build_parser, run


def test_dispatcher_parser_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_dispatcher_routes_to_server(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, list[str]] = {}
    fake_module = types.SimpleNamespace(
        run=lambda argv=None: captured.setdefault("server", list(argv or []))
    )
    monkeypatch.setitem(__import__("sys").modules, "bangstats_server.app", fake_module)

    run(["server", "--host", "127.0.0.1", "--port", "9000"])
    assert captured["server"] == ["--host", "127.0.0.1", "--port", "9000"]


def test_dispatcher_routes_to_client(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, list[str]] = {}
    fake_module = types.SimpleNamespace(
        run=lambda argv=None: captured.setdefault("client", list(argv or []))
    )
    monkeypatch.setitem(__import__("sys").modules, "bangstats_cli.app", fake_module)

    run(["client", "--server-url", "http://localhost:8000", "--skip-sync"])
    assert captured["client"] == ["--server-url", "http://localhost:8000", "--skip-sync"]

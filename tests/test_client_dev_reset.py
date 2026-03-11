import httpx

from bangstats_cli import app as client_app


class _FakeAPI:
    def __init__(self):
        self.sync_calls = 0
        self.flushed = False
        self.prepared_calls = []
        self.updated_payloads = []

    def flush(self, **_kwargs):
        self.flushed = True
        return {"backup_root": "/tmp/backup"}

    def create_sync_job(self, _server: str, requested_by_user_id: int | None = None):
        self.sync_calls += 1
        if self.sync_calls == 1:
            request = httpx.Request("POST", "http://localhost:8000/api/sync/jobs")
            response = httpx.Response(401, request=request, json={"detail": "Unauthorized"})
            raise httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        return {"id": 3, "status": "queued", "requested_by_user_id": requested_by_user_id}

    def dev_seed(self, *, user_id: int, count: int = 100):
        _ = user_id
        _ = count
        return {"seeded": 0, "attempted": 0, "requested": 0}

    def dev_config(self):
        return {"fake_time_span_days": 90}

    def dev_prepare_simulated_folders(
        self,
        *,
        user_id: int,
        target: str,
        count: int = 20,
        time_span_days: int = 90,
        clear_existing: bool = True,
    ):
        self.prepared_calls.append(
            {
                "user_id": user_id,
                "target": target,
                "count": count,
                "time_span_days": time_span_days,
                "clear_existing": clear_existing,
            }
        )
        return {
            "local_path": "/tmp/dev/local_source" if target in {"local", "both"} else None,
            "local_created": count if target in {"local", "both"} else None,
            "local_existing_before": 3 if target in {"local", "both"} else None,
            "server_path": "/tmp/dev/server_folder" if target in {"server", "both"} else None,
            "server_created": count if target in {"server", "both"} else None,
            "server_existing_before": 2 if target in {"server", "both"} else None,
        }

    def update_user(self, _user_id: int, payload: dict):
        self.updated_payloads.append(payload)
        return {"id": 1, "username": "dev_user", "server": "en", **payload}


def test_dev_tools_reset_relogin_retry(monkeypatch):
    api = _FakeAPI()
    starting_user = {"id": 1, "username": "dev_user", "server": "en"}
    relogged_user = {"id": 9, "username": "dev_user", "server": "en"}

    answers = iter(["2", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(client_app, "_dev_auto_login", lambda _api: relogged_user)

    result_user = client_app._dev_tools_menu(api, starting_user, "en")

    assert api.flushed is True
    assert api.sync_calls == 2
    assert result_user == relogged_user


def test_dev_tools_prepare_local_shows_counts_and_updates_path(monkeypatch, capsys):
    api = _FakeAPI()
    starting_user = {"id": 1, "username": "dev_user", "server": "en"}
    answers = iter(["4", "", "", "", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    result_user = client_app._dev_tools_menu(api, starting_user, "en")
    output = capsys.readouterr().out

    assert len(api.prepared_calls) == 1
    assert api.prepared_calls[0]["target"] == "local"
    assert api.prepared_calls[0]["count"] == 20
    assert api.prepared_calls[0]["time_span_days"] == 90
    assert api.prepared_calls[0]["clear_existing"] is True
    assert "existing_before=3" in output
    assert "created=20" in output
    assert api.updated_payloads[0]["screenshots_source"] == "local"
    assert api.updated_payloads[0]["screenshots_path"] == "/tmp/dev/local_source"
    assert result_user["screenshots_source"] == "local"


def test_dev_tools_prepare_server_clamps_count_to_api_limit(monkeypatch, capsys):
    api = _FakeAPI()
    starting_user = {"id": 1, "username": "dev_user", "server": "en"}
    answers = iter(["5", "17000", "", "", "n", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    client_app._dev_tools_menu(api, starting_user, "en")
    output = capsys.readouterr().out

    assert len(api.prepared_calls) == 1
    assert api.prepared_calls[0]["target"] == "server"
    assert api.prepared_calls[0]["count"] == 10000
    assert "Value too large (max 10000), using 10000." in output

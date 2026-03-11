from pathlib import Path

from bangstats_cli import menus


class _FakeAPI:
    def __init__(self):
        self.updated_payloads = []
        self.created_jobs = []
        self.uploaded_batches = []
        self.authorize_calls = 0

    def update_user(self, _user_id: int, payload: dict):
        self.updated_payloads.append(payload)
        response = {
            "id": 7,
            "username": "u",
            "game_id": "gid",
            "server": "en",
            "screenshots_source": payload.get("screenshots_source", "local"),
            "screenshots_path": payload.get("screenshots_path", ""),
            "server_folder_authorized": payload.get("server_folder_authorized", False),
            "sync_command": payload.get("sync_command"),
        }
        return response

    def get_scan_capabilities(self):
        return {"provider": "fake", "available_google_keys": 0}

    def get_scan_filename_diff(self, *, user_id: int, filenames: list[str]):
        return {
            "requested_total": len(filenames),
            "already_scanned_count": 0,
            "to_scan_count": len(filenames),
            "to_scan_filenames": filenames,
        }

    def upload_scan_files(self, user_id: int, image_paths: list[Path]):
        self.uploaded_batches.append((user_id, [p.name for p in image_paths]))
        return {
            "uploaded_files": len(image_paths),
            "total_uploaded_for_user": len(image_paths),
            "total_storage_mb_for_user": 0.1,
        }

    def create_scan_job(self, **kwargs):
        self.created_jobs.append(kwargs)
        return {"id": 99, "status": "queued", "total_files": len(kwargs.get("filenames", []))}

    def authorize_server_folder(self, *, master_key: str):
        self.authorize_calls += 1
        return {"authorized": master_key == "ok"}

    def get_user(self, _user_id: int):
        return {
            "id": 7,
            "username": "u",
            "game_id": "gid",
            "server": "en",
            "screenshots_source": "server_folder",
            "screenshots_path": "",
            "server_folder_authorized": True,
            "sync_command": None,
        }

    def dev_config(self):
        return {
            "dev_simulate_screenshot_locations": True,
            "dev_simulated_server_folder_root": "/tmp/dev-server-root",
            "dev_simulated_client_upload_source_root": "/tmp/dev-local-root",
            "fake_time_span_days": 90,
        }

    def check_scan_local_path_for_user(self, *, folder_path: str, user_id: int):
        _ = user_id
        return {"is_local": True, "canonical_path": folder_path}


class _FailingUpdateAPI(_FakeAPI):
    def update_user(self, _user_id: int, _payload: dict):
        raise RuntimeError("forced update failure")


def test_screenshot_location_setup_first_time_local(monkeypatch, tmp_path: Path):
    api = _FakeAPI()
    local_dir = tmp_path / "shots"
    local_dir.mkdir(parents=True, exist_ok=True)
    user = {
        "id": 7,
        "username": "u",
        "game_id": "gid",
        "server": "en",
        "screenshots_source": "local",
        "screenshots_path": "",
    }
    answers = iter(["1", str(local_dir)])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    updated = menus.screenshot_location_setup(api, user)
    assert updated["screenshots_source"] == "local"
    assert updated["screenshots_path"] == str(local_dir)


def test_scan_screenshots_local_creates_job_and_returns(monkeypatch, tmp_path: Path):
    api = _FakeAPI()
    local_dir = tmp_path / "shots"
    local_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(3):
        (local_dir / f"Screenshot_{idx}.png").write_bytes(b"x")

    user = {
        "id": 7,
        "username": "u",
        "game_id": "gid",
        "server": "en",
        "screenshots_source": "local",
        "screenshots_path": str(local_dir),
        "server_folder_authorized": False,
    }

    answers = iter(["y"])  # keep current screenshot settings
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    menus.scan_screenshots(api, user)

    assert len(api.uploaded_batches) == 1
    assert len(api.created_jobs) == 1
    assert api.created_jobs[0]["source_type"] == "upload"


def test_screenshot_location_setup_dev_mode_reuses_production_choices(monkeypatch):
    api = _FakeAPI()
    user = {
        "id": 7,
        "username": "u",
        "game_id": "gid",
        "server": "en",
        "screenshots_source": "local",
        "screenshots_path": "",
        "server_folder_authorized": False,
    }
    answers = iter(["3"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    updated = menus.screenshot_location_setup(
        api,
        user,
        dev_mode=True,
        dev_config=api.dev_config(),
    )
    assert updated is user
    assert api.updated_payloads == []


def test_screenshot_location_setup_dev_choice_handles_update_error(monkeypatch):
    api = _FailingUpdateAPI()
    local_dir = Path("/tmp")
    user = {
        "id": 7,
        "username": "u",
        "game_id": "gid",
        "server": "en",
        "screenshots_source": "local",
        "screenshots_path": "",
        "server_folder_authorized": False,
    }
    answers = iter(["1", str(local_dir)])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    updated = menus.screenshot_location_setup(
        api,
        user,
        dev_mode=True,
        dev_config=api.dev_config(),
    )
    assert updated is user


def test_scan_screenshots_dev_server_choice_auth_fail_does_not_fallback_local(
    monkeypatch,
):
    api = _FakeAPI()
    user = {
        "id": 7,
        "username": "u",
        "game_id": "gid",
        "server": "en",
        "screenshots_source": "local",
        "screenshots_path": "",
        "server_folder_authorized": False,
    }

    answers = iter(["2"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(menus, "getpass", lambda _prompt="": "")

    menus.scan_screenshots(
        api,
        user,
        dev_mode=True,
        dev_config=api.dev_config(),
    )

    assert api.uploaded_batches == []
    assert api.created_jobs == []

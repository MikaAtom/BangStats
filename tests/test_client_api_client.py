from pathlib import Path
from typing import Any

from bangstats_cli.api_client import BangStatsAPI


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttpxClient:
    def __init__(self, batch_payloads: list[dict[str, Any]]):
        self._batch_payloads = batch_payloads
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}

    def post(self, url: str, *, data=None, files=None, json=None, timeout=None):
        self.calls.append(
            {
                "method": "post",
                "url": url,
                "data": data,
                "files_count": len(files) if files else 0,
                "json": json,
                "timeout": timeout,
            }
        )
        if url == "/api/scans":
            call_index = len([c for c in self.calls if c["url"] == "/api/scans"]) - 1
            payload = self._batch_payloads[call_index]
            return _FakeResponse(payload)
        if url == "/api/scans/filename-diff":
            return _FakeResponse(
                {
                    "requested_total": len(json["filenames"]),
                    "already_scanned_count": 1,
                    "to_scan_count": max(0, len(json["filenames"]) - 1),
                    "already_scanned_filenames": json["filenames"][:1],
                    "to_scan_filenames": json["filenames"][1:],
                }
            )
        if url == "/api/scans/check-local-path":
            return _FakeResponse(
                {"is_local": True, "canonical_path": json["folder_path"]}
            )
        if url == "/api/scans/authorize-server-folder":
            return _FakeResponse({"authorized": json["master_key"] == "ok"})
        if url == "/api/scans/upload":
            return _FakeResponse(
                {
                    "uploaded_files": len(files or []),
                    "total_uploaded_for_user": len(files or []),
                    "total_storage_mb_for_user": 1.5,
                }
            )
        if url == "/api/scans/jobs":
            return _FakeResponse(
                {
                    "id": 55,
                    "user_id": json["user_id"],
                    "status": "queued",
                    "source_type": json["source_type"],
                    "folder_path": json.get("folder_path"),
                    "cancelled": False,
                    "total_files": len(json.get("filenames") or []),
                    "processed": 0,
                    "successful": 0,
                    "validated": 0,
                    "persisted": 0,
                    "failed_to_persist": 0,
                    "skipped_duplicates": 0,
                    "errors": {},
                    "error_files": {},
                    "parallel_workers": json.get("parallel_workers"),
                    "keys_per_worker": json.get("keys_per_worker"),
                    "created_at": "2026-03-01T00:00:00",
                    "started_at": None,
                    "finished_at": None,
                    "error_message": None,
                }
            )
        if url.startswith("/api/scans/jobs/") and url.endswith("/cancel"):
            return _FakeResponse(
                {
                    "id": int(url.split("/")[-2]),
                    "user_id": 7,
                    "status": "cancelled",
                    "source_type": "upload",
                    "folder_path": None,
                    "cancelled": True,
                    "total_files": 10,
                    "processed": 3,
                    "successful": 2,
                    "validated": 2,
                    "persisted": 2,
                    "failed_to_persist": 0,
                    "skipped_duplicates": 0,
                    "errors": {},
                    "error_files": {},
                    "parallel_workers": None,
                    "keys_per_worker": None,
                    "created_at": "2026-03-01T00:00:00",
                    "started_at": "2026-03-01T00:01:00",
                    "finished_at": "2026-03-01T00:02:00",
                    "error_message": "Cancelled by user",
                }
            )
        if url == "/api/scans/scan-local-folder":
            return _FakeResponse(
                {
                    "total_scanned": len(json["filenames"]),
                    "successful": len(json["filenames"]),
                    "errors": {},
                    "error_files": {},
                    "validated": len(json["filenames"]),
                    "persisted": len(json["filenames"]),
                    "failed_to_persist": 0,
                    "skipped_duplicates": 0,
                    "error_rate": 0.0,
                    "additional": {},
                }
            )
        if url == "/api/auth/register":
            return _FakeResponse(
                {
                    "token": "register-token",
                    "user": {"id": 7, "username": json["username"], "server": "en"},
                }
            )
        if url == "/api/auth/login":
            return _FakeResponse(
                {
                    "token": "login-token",
                    "user": {"id": 7, "username": json["username"], "server": "en"},
                }
            )
        if url == "/api/auth/logout":
            return _FakeResponse({"status": "ok"})
        if url == "/api/dev/prepare-simulated-folders":
            target = str(json["target"])
            payload: dict[str, Any] = {
                "local_path": None,
                "local_created": None,
                "local_existing_before": None,
                "server_path": None,
                "server_created": None,
                "server_existing_before": None,
            }
            if target in {"local", "both"}:
                payload["local_path"] = "/tmp/local_source"
                payload["local_created"] = int(json["count"])
                payload["local_existing_before"] = 2
            if target in {"server", "both"}:
                payload["server_path"] = "/tmp/server_folder"
                payload["server_created"] = int(json["count"])
                payload["server_existing_before"] = 1
            return _FakeResponse(payload)
        raise AssertionError(f"Unexpected URL in fake client: {url}")

    def get(self, url: str, *, params=None):
        self.calls.append({"method": "get", "url": url, "params": params})
        if "/stats/milestones" in url:
            return _FakeResponse(
                {
                    "milestones": [
                        {
                            "type": "first_play",
                            "label": "First play recorded",
                            "play_count": 1,
                            "meta": {"timestamp": "2026-03-01T12:00:00", "filename": "a.png"},
                        }
                    ],
                    "best_streak_days": 3,
                    "current_streak_days": 2,
                }
            )
        if "/stats/activity" in url:
            return _FakeResponse(
                {
                    "from_date": "2026-03-01",
                    "to_date": "2026-03-31",
                    "days": 31,
                    "summary": {
                        "total_plays": 42,
                        "total_fc": 10,
                        "total_ap": 3,
                        "accuracy": 95.2,
                    },
                    "active_days": 12,
                    "avg_plays_per_day": 1.35,
                    "range_streak_days": 4,
                    "delta_vs_previous": {
                        "plays_delta": 5,
                        "plays_delta_pct": 13.51,
                        "accuracy_delta": 0.8,
                    },
                }
            )
        if "/stats/calendar" in url:
            return _FakeResponse(
                {
                    "year": 2026,
                    "month": 3,
                    "total_days_with_plays": 1,
                    "days": [
                        {
                            "date": "2026-03-01",
                            "plays": 2,
                            "fc": 1,
                            "ap": 0,
                            "accuracy": 95.0,
                            "difficulties": {"expert": 2},
                        }
                    ],
                }
            )
        if "/stats/songs/search" in url:
            return _FakeResponse(
                {
                    "query": params["q"],
                    "limit": int(params["limit"]),
                    "results": [
                        {
                            "song_id": 125,
                            "song_name": "Unite! From A To Z",
                        }
                    ],
                }
            )
        if "/stats/songs/" in url:
            return _FakeResponse(
                {
                    "song_id": 125,
                    "song_name": "Unite! From A To Z",
                    "requested_difficulty": params.get("difficulty"),
                    "difficulty_overview": [
                        {
                            "difficulty": "hard",
                            "total_plays": 2,
                            "first_played": {
                                "timestamp": "2026-03-01T12:00:00",
                                "filename": "a.png",
                            },
                        }
                    ],
                    "detail": {
                        "total_plays": 2,
                        "total_fc": 1,
                        "total_ap": 0,
                        "accuracy": 95.0,
                        "first_played": {
                            "timestamp": "2026-03-01T12:00:00",
                            "filename": "a.png",
                        },
                        "last_played": {
                            "timestamp": "2026-03-02T12:00:00",
                            "filename": "b.png",
                        },
                        "first_fc": {
                            "timestamp": "2026-03-02T12:00:00",
                            "filename": "b.png",
                        },
                        "last_fc": {
                            "timestamp": "2026-03-02T12:00:00",
                            "filename": "b.png",
                        },
                        "first_ap": None,
                        "last_ap": None,
                        "plays_before_fc": 1,
                        "plays_before_ap": None,
                    }
                    if params.get("difficulty")
                    else None,
                }
            )
        if url == "/api/reference/counts":
            return _FakeResponse({"songs": 3, "events": 2, "bands": 1})
        if url == "/api/reference/songs":
            return _FakeResponse(
                {"max_id": 10, "items": [{"id": params["since_id"] + 1}]}
            )
        if url == "/api/reference/events":
            return _FakeResponse(
                {"max_id": 11, "items": [{"id": params["since_id"] + 1}]}
            )
        if url == "/api/reference/bands":
            return _FakeResponse(
                {"max_id": 12, "items": [{"id": params["since_id"] + 1}]}
            )
        if url == "/api/scans/jobs":
            return _FakeResponse(
                {
                    "jobs": [
                        {
                            "id": 55,
                            "user_id": 7,
                            "status": "running",
                            "source_type": "upload",
                            "folder_path": None,
                            "cancelled": False,
                            "total_files": 10,
                            "processed": 2,
                            "successful": 2,
                            "validated": 2,
                            "persisted": 2,
                            "failed_to_persist": 0,
                            "skipped_duplicates": 0,
                            "errors": {},
                            "error_files": {},
                            "parallel_workers": None,
                            "keys_per_worker": None,
                            "created_at": "2026-03-01T00:00:00",
                            "started_at": "2026-03-01T00:01:00",
                            "finished_at": None,
                            "error_message": None,
                        }
                    ]
                }
            )
        if url.startswith("/api/scans/jobs/"):
            return _FakeResponse(
                {
                    "id": int(url.split("/")[-1]),
                    "user_id": 7,
                    "status": "running",
                    "source_type": "upload",
                    "folder_path": None,
                    "cancelled": False,
                    "total_files": 10,
                    "processed": 5,
                    "successful": 5,
                    "validated": 5,
                    "persisted": 5,
                    "failed_to_persist": 0,
                    "skipped_duplicates": 0,
                    "errors": {},
                    "error_files": {},
                    "parallel_workers": None,
                    "keys_per_worker": None,
                    "created_at": "2026-03-01T00:00:00",
                    "started_at": "2026-03-01T00:01:00",
                    "finished_at": None,
                    "error_message": None,
                }
            )
        if url == "/api/scans/upload-usage":
            return _FakeResponse({"file_count": 4, "total_size_mb": 2.2, "oldest_file_age_days": 3.5})
        raise AssertionError(f"Unexpected URL in fake client.get: {url}")

    def close(self) -> None:
        return None


def test_scan_images_batches_upload_and_aggregates(tmp_path: Path):
    files: list[Path] = []
    for idx in range(205):
        target = tmp_path / f"Screenshot_{idx}.png"
        target.write_bytes(b"x")
        files.append(target)

    batch_a = {
        "total_scanned": 200,
        "successful": 190,
        "validated": 190,
        "persisted": 180,
        "failed_to_persist": 5,
        "skipped_duplicates": 5,
        "errors": {"not_found_errors": 10},
        "error_files": {"not_found_errors": ["a.json"]},
        "additional": {"provider": "gemini", "parallel_enabled": False},
    }
    batch_b = {
        "total_scanned": 5,
        "successful": 5,
        "validated": 5,
        "persisted": 4,
        "failed_to_persist": 0,
        "skipped_duplicates": 1,
        "errors": {"not_found_errors": 0},
        "error_files": {"not_found_errors": ["b.json"]},
        "additional": {"provider": "gemini", "parallel_enabled": False},
    }

    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([batch_a, batch_b])
    api._client = fake_client
    api.SCAN_UPLOAD_BATCH_SIZE = 200

    result = api.scan_images(user_id=3, image_paths=files)

    assert len(fake_client.calls) == 2
    assert fake_client.calls[0]["files_count"] == 200
    assert fake_client.calls[1]["files_count"] == 5
    assert all(call["timeout"] is None for call in fake_client.calls)

    assert result["total_scanned"] == 205
    assert result["successful"] == 195
    assert result["persisted"] == 184
    assert result["failed_to_persist"] == 5
    assert result["skipped_duplicates"] == 6
    assert result["errors"]["not_found_errors"] == 10
    assert result["error_files"]["not_found_errors"] == ["a.json", "b.json"]
    assert result["additional"]["upload_mode"] == "chunked"
    assert result["additional"]["upload_batches"] == 2
    assert result["additional"]["upload_batch_size"] == 200


def test_precheck_and_local_scan_client_methods():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    diff = api.get_scan_filename_diff(user_id=7, filenames=["a.png", "b.png"])
    assert diff["requested_total"] == 2
    assert diff["already_scanned_filenames"] == ["a.png"]
    assert diff["to_scan_filenames"] == ["b.png"]

    local = api.check_scan_local_path("/srv/data/BangStats/user/screens")
    assert local["is_local"] is True
    assert local["canonical_path"] == "/srv/data/BangStats/user/screens"

    result = api.scan_local_folder(
        user_id=7,
        folder_path="/srv/data/BangStats/user/screens",
        filenames=["b.png"],
        parallel_workers=2,
        keys_per_worker=1,
    )
    assert result["total_scanned"] == 1
    assert result["persisted"] == 1


def test_song_stats_client_methods():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    search = api.search_user_stat_songs(
        user_id=7,
        query="unite",
        server="en",
        limit=10,
    )
    assert search["query"] == "unite"
    assert search["results"][0]["song_id"] == 125

    overview = api.get_user_song_stats(user_id=7, song_id=125, server="en")
    assert overview["song_id"] == 125
    assert overview["detail"] is None

    detail = api.get_user_song_stats(
        user_id=7,
        song_id=125,
        server="en",
        difficulty="hard",
    )
    assert detail["requested_difficulty"] == "hard"
    assert detail["detail"]["total_plays"] == 2


def test_expanded_stats_client_methods():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    milestones = api.get_user_stats_milestones(user_id=7)
    assert milestones["best_streak_days"] == 3

    activity = api.get_user_stats_activity(user_id=7, preset="30d")
    assert activity["summary"]["total_plays"] == 42

    custom_activity = api.get_user_stats_activity(
        user_id=7,
        preset=None,
        from_date="2026-03-01",
        to_date="2026-03-31",
    )
    assert custom_activity["days"] == 31

    calendar = api.get_user_stats_calendar(user_id=7, year=2026, month=3)
    assert calendar["total_days_with_plays"] == 1


def test_auth_methods_and_auth_header_management():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    api.set_auth_token("abc")
    assert api._token == "abc"
    assert fake_client.headers["Authorization"] == "Bearer abc"

    api.set_auth_token(None)
    assert api._token is None
    assert "Authorization" not in fake_client.headers

    register_payload = api.register(
        {"username": "tester", "password": "pw", "game_id": "gid", "server": "en"}
    )
    assert register_payload["token"] == "register-token"
    assert api._token == "register-token"
    assert fake_client.headers["Authorization"] == "Bearer register-token"

    login_payload = api.login("tester", "pw")
    assert login_payload["token"] == "login-token"
    assert api._token == "login-token"
    assert fake_client.headers["Authorization"] == "Bearer login-token"

    api.logout()
    assert api._token is None
    assert "Authorization" not in fake_client.headers


def test_reference_methods():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    counts = api.get_reference_counts()
    assert counts == {"songs": 3, "events": 2, "bands": 1}

    songs = api.get_reference_songs(since_id=5, limit=10)
    assert songs["items"][0]["id"] == 6

    events = api.get_reference_events(since_id=8, limit=10)
    assert events["items"][0]["id"] == 9

    bands = api.get_reference_bands(since_id=1, limit=10)
    assert bands["items"][0]["id"] == 2


def test_scan_job_methods_and_upload_usage(tmp_path: Path):
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    files = []
    for idx in range(3):
        path = tmp_path / f"{idx}.png"
        path.write_bytes(b"x")
        files.append(path)

    auth = api.authorize_server_folder(master_key="ok")
    assert auth["authorized"] is True

    uploaded = api.upload_scan_files(7, files)
    assert uploaded["uploaded_files"] == 3

    created = api.create_scan_job(user_id=7, source_type="upload", filenames=["0.png", "1.png"])
    assert created["status"] == "queued"
    assert created["source_type"] == "upload"

    listed = api.list_scan_jobs(limit=5, status="running")
    assert listed["jobs"][0]["status"] == "running"

    detail = api.get_scan_job(55)
    assert detail["id"] == 55

    cancelled = api.cancel_scan_job(55)
    assert cancelled["status"] == "cancelled"

    usage = api.get_upload_usage(user_id=7)
    assert usage["file_count"] == 4

    prepared = api.dev_prepare_simulated_folders(
        user_id=7,
        target="both",
        count=6,
        time_span_days=15,
        clear_existing=False,
    )
    assert prepared["local_created"] == 6
    assert prepared["server_created"] == 6

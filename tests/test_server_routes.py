import uuid
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bangstats_server.app import app
from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import scans as scans_router
from bangstats_server.api.routers import stats as stats_router
from bangstats_server.api.routers import sync as sync_router


@pytest.fixture(autouse=True)
def _auth_override():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7,
        username="test",
        game_id="gid",
        server="en",
        server_folder_authorized=True,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_health_route():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["mode"] in {"production", "dev"}


def test_user_crud_routes():
    with TestClient(app) as client:
        suffix = uuid.uuid4().hex[:8]
        username = f"test_user_{suffix}"
        game_id = f"gid_{suffix}"

        create_response = client.post(
            "/api/users",
            json={
                "game_id": game_id,
                "username": username,
                "server": "en",
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["username"] == username
        assert created["game_id"] == game_id

        user_id = int(created["id"])
        get_response = client.get(f"/api/users/{user_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == user_id

        update_response = client.patch(
            f"/api/users/{user_id}",
            json={"screenshots_path": "/tmp/screenshots"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["screenshots_path"] == "/tmp/screenshots"


def test_stats_song_search_route(monkeypatch):
    song_a = SimpleNamespace(
        internal_song_id=125,
        name={"en": "Unite! From A To Z", "jp": "Unite! From A To Z"},
    )
    song_b = SimpleNamespace(
        internal_song_id=812,
        name={"en": "Unite from A to Z (Cover)"},
    )

    class _FakeSongService:
        def search_songs_by_name(self, name_query, language="en"):
            assert "unite" in name_query.lower()
            if language == "en":
                return [song_a, song_b]
            if language == "jp":
                return [song_a]
            return []

    monkeypatch.setattr(stats_router, "song_service", _FakeSongService())

    with TestClient(app) as client:
        response = client.get(
            "/api/users/7/stats/songs/search",
            params={"q": "unite", "server": "en", "limit": 2},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["query"] == "unite"
        assert payload["limit"] == 2
        assert len(payload["results"]) == 2
        assert {row["song_id"] for row in payload["results"]} == {125, 812}


def test_stats_song_detail_route_with_difficulty(monkeypatch):
    base_time = datetime(2026, 3, 1, 12, 0, 0)
    song = SimpleNamespace(
        internal_song_id=125,
        name={"en": "Unite! From A To Z"},
        length=120.0,
    )
    hard_play_a = SimpleNamespace(
        difficulty="hard",
        timestamp=base_time,
        filename="a.png",
        perfect=100,
        great=10,
        good=0,
        bad=0,
        miss=0,
        full_combo=False,
        all_perfect=False,
    )
    hard_play_b = SimpleNamespace(
        difficulty="hard",
        timestamp=base_time,
        filename="b.png",
        perfect=110,
        great=0,
        good=0,
        bad=0,
        miss=0,
        full_combo=True,
        all_perfect=True,
    )
    expert_play = SimpleNamespace(
        difficulty="expert",
        timestamp=base_time,
        filename="c.png",
        perfect=90,
        great=5,
        good=0,
        bad=0,
        miss=0,
        full_combo=True,
        all_perfect=False,
    )

    class _FakeSongService:
        def get_song_by_internal_id(self, song_id):
            assert song_id == 125
            return song

    class _FakeScreenshotService:
        def get_screenshots_by_song(self, user_id, song_id, difficulty=None):
            assert user_id == 7
            assert song_id == 125
            if difficulty is None:
                return [hard_play_a, hard_play_b, expert_play]
            if difficulty == "hard":
                return [hard_play_a, hard_play_b]
            return []

    monkeypatch.setattr(stats_router, "song_service", _FakeSongService())
    monkeypatch.setattr(stats_router, "screenshot_service", _FakeScreenshotService())

    with TestClient(app) as client:
        response = client.get(
            "/api/users/7/stats/songs/125",
            params={"server": "en", "difficulty": "hard"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["song_id"] == 125
        assert payload["requested_difficulty"] == "hard"
        assert len(payload["difficulty_overview"]) == 2
        assert payload["difficulty_overview"][0]["estimated_time_played_seconds"] >= 240
        assert payload["detail"]["total_plays"] == 2
        assert payload["detail"]["total_fc"] == 1
        assert payload["detail"]["estimated_time_played_seconds"] == 240
        assert payload["detail"]["total_sessions"] >= 1


def test_stats_song_detail_route_returns_404_without_plays(monkeypatch):
    class _FakeSongService:
        def get_song_by_internal_id(self, song_id):
            return SimpleNamespace(internal_song_id=song_id, name={"en": "Song Name"})

    class _FakeScreenshotService:
        def get_screenshots_by_song(self, user_id, song_id, difficulty=None):
            return []

    monkeypatch.setattr(stats_router, "song_service", _FakeSongService())
    monkeypatch.setattr(stats_router, "screenshot_service", _FakeScreenshotService())

    with TestClient(app) as client:
        response = client.get(
            "/api/users/7/stats/songs/125",
            params={"server": "en"},
        )
        assert response.status_code == 404
        assert "no plays found" in response.json()["detail"].lower()


def test_stats_milestones_route(monkeypatch):
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        SimpleNamespace(
            song_id=10,
            difficulty="expert",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=False,
            all_perfect=False,
            filename="a.png",
        ),
        SimpleNamespace(
            song_id=10,
            difficulty="expert",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=True,
            all_perfect=False,
            filename="b.png",
        ),
    ]

    class _FakeScreenshotService:
        def get_screenshots_by_user(self, user_id):
            assert user_id == 7
            return plays

    monkeypatch.setattr(stats_router, "screenshot_service", _FakeScreenshotService())
    with TestClient(app) as client:
        response = client.get("/api/users/7/stats/milestones")
        assert response.status_code == 200
        payload = response.json()
        assert payload["best_streak_days"] >= 1
        assert isinstance(payload["milestones"], list)


def test_stats_activity_route_preset_and_custom(monkeypatch):
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        SimpleNamespace(
            song_id=10,
            difficulty="expert",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=True,
            all_perfect=False,
            filename="a.png",
        )
    ]

    class _FakeScreenshotService:
        def get_screenshots_by_user(self, _user_id):
            return plays

    monkeypatch.setattr(stats_router, "screenshot_service", _FakeScreenshotService())
    with TestClient(app) as client:
        preset_response = client.get("/api/users/7/stats/activity", params={"preset": "7d"})
        assert preset_response.status_code == 200
        custom_response = client.get(
            "/api/users/7/stats/activity",
            params={"from_date": "2026-03-01", "to_date": "2026-03-31"},
        )
        assert custom_response.status_code == 200
        bad_response = client.get("/api/users/7/stats/activity", params={"preset": "2d"})
        assert bad_response.status_code == 400


def test_stats_calendar_route(monkeypatch):
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        SimpleNamespace(
            song_id=10,
            difficulty="expert",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=True,
            all_perfect=False,
            filename="a.png",
        )
    ]

    class _FakeScreenshotService:
        def get_screenshots_by_user(self, _user_id):
            return plays

    monkeypatch.setattr(stats_router, "screenshot_service", _FakeScreenshotService())
    with TestClient(app) as client:
        response = client.get("/api/users/7/stats/calendar", params={"year": 2026, "month": 3})
        assert response.status_code == 200
        payload = response.json()
        assert payload["year"] == 2026
        assert payload["month"] == 3


def test_stats_insights_route(monkeypatch):
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        SimpleNamespace(
            song_id=10,
            difficulty="expert",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=True,
            all_perfect=False,
            filename="a.png",
        ),
        SimpleNamespace(
            song_id=10,
            difficulty="expert",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=True,
            all_perfect=False,
            filename="b.png",
        ),
        SimpleNamespace(
            song_id=11,
            difficulty="hard",
            timestamp=base,
            perfect=100,
            great=0,
            good=0,
            bad=0,
            miss=0,
            full_combo=True,
            all_perfect=False,
            filename="c.png",
        ),
    ]

    class _FakeScreenshotService:
        def get_screenshots_by_user(self, _user_id):
            return plays

    class _FakeSongService:
        def get_song_by_internal_id(self, song_id):
            if song_id == 10:
                return SimpleNamespace(internal_song_id=10, name={"en": "Song Ten"}, length=120.0)
            if song_id == 11:
                return SimpleNamespace(internal_song_id=11, name={"en": "Song Eleven"}, length=150.0)
            return None

    monkeypatch.setattr(stats_router, "screenshot_service", _FakeScreenshotService())
    monkeypatch.setattr(stats_router, "song_service", _FakeSongService())
    with TestClient(app) as client:
        response = client.get(
            "/api/users/7/stats/insights",
            params={
                "from_date": "2026-03-01",
                "to_date": "2026-03-31",
                "session_gap_minutes": 45,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_quality"]["observed_plays"] == 3
        assert payload["session_gap_minutes"] == 45
        assert isinstance(payload["repetition"]["most_looped_songs"], list)


def test_import_json_folder_route(monkeypatch):
    class _FakeScanService:
        def import_json_folder(self, *, folder_path, user_id, persist_to_db):
            assert folder_path == "/tmp/legacy-json"
            assert user_id == 7
            assert persist_to_db is True
            return {
                "total_scanned": 2,
                "successful": 1,
                "errors": {
                    "note_errors": 1,
                    "not_found_errors": 0,
                    "fast_slow_errors": 0,
                    "max_combo_errors": 0,
                    "live_errors": 0,
                    "validation_errors": 0,
                },
                "error_files": {"note_errors": ["Screenshot_1.png"]},
                "validated": 1,
                "persisted": 1,
                "failed_to_persist": 0,
                "skipped_duplicates": 0,
                "error_rate": 50.0,
                "additional": {},
            }

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)

    with TestClient(app) as client:
        response = client.post(
            "/api/scans/import-json-folder",
            json={
                    "user_id": 7,
                "folder_path": "/tmp/legacy-json",
                "persist_to_db": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_scanned"] == 2
        assert payload["persisted"] == 1


def test_scan_error_routes(monkeypatch):
    class _FakeScanService:
        def list_error_files(self):
            return {
                "total": 1,
                "errors": {"note_errors": 1},
                "error_files": {"note_errors": ["Screenshot_1.json"]},
            }

        def get_error_detail(self, error_type, json_filename):
            assert error_type == "note_errors"
            assert json_filename == "Screenshot_1.json"
            return {
                "error_type": error_type,
                "json_filename": json_filename,
                "image_filename": "Screenshot_1.png",
                "scan_data": {"song_name_from_top_bar_text": "Test Song"},
                "validation": {"error_type": "note_errors"},
            }

        def correct_error_file(
            self,
            *,
            user_id,
            error_type,
            json_filename,
            corrected_scan_data,
            persist_to_db,
        ):
            assert user_id == 7
            assert error_type == "note_errors"
            assert json_filename == "Screenshot_1.json"
            assert corrected_scan_data["song_name_from_top_bar_text"] == "Fixed Song"
            assert persist_to_db is True
            return {
                "image_filename": "Screenshot_1.png",
                "is_valid": True,
                "error_type": None,
                "persisted": True,
                "skipped_duplicates": False,
                "failed_to_persist": False,
            }

        def revalidate_error_category(
            self,
            *,
            user_id,
            error_type,
            persist_to_db,
            progress_every,
        ):
            assert user_id == 7
            assert error_type == "note_errors"
            assert persist_to_db is True
            assert progress_every == 123
            return {
                "total_files": 2,
                "processed": 2,
                "successful": 1,
                "persisted": 1,
                "skipped_duplicates": 0,
                "failed_to_persist": 0,
                "missing_image": 0,
                "scan_failed": 0,
                "errors": {"note_errors": 1},
            }

        def rescan_error_category(
            self,
            *,
            user_id,
            error_type,
            persist_to_db,
            progress_every,
            model,
        ):
            assert user_id == 7
            assert error_type == "note_errors"
            assert persist_to_db is True
            assert progress_every == 123
            assert model == "gemini-2.5-flash"
            return {
                "total_files": 2,
                "processed": 2,
                "successful": 0,
                "persisted": 0,
                "skipped_duplicates": 0,
                "failed_to_persist": 0,
                "missing_image": 2,
                "scan_failed": 0,
                "errors": {},
            }

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)

    with TestClient(app) as client:
        list_response = client.get("/api/scans/errors")
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        detail_response = client.get("/api/scans/errors/note_errors/Screenshot_1.json")
        assert detail_response.status_code == 200
        assert detail_response.json()["image_filename"] == "Screenshot_1.png"

        correction_response = client.post(
            "/api/scans/errors/note_errors/Screenshot_1.json/correct",
            json={
                "user_id": 7,
                "corrected_scan_data": {"song_name_from_top_bar_text": "Fixed Song"},
                "persist_to_db": True,
            },
        )
        assert correction_response.status_code == 200
        assert correction_response.json()["persisted"] is True

        revalidate_response = client.post(
            "/api/scans/errors/note_errors/revalidate",
            json={"user_id": 7, "persist_to_db": True, "progress_every": 123},
        )
        assert revalidate_response.status_code == 200
        assert revalidate_response.json()["processed"] == 2

        rescan_response = client.post(
            "/api/scans/errors/note_errors/rescan",
            json={
                "user_id": 7,
                "persist_to_db": True,
                "progress_every": 123,
                "model": "gemini-2.5-flash",
            },
        )
        assert rescan_response.status_code == 200
        assert rescan_response.json()["missing_image"] == 2


def test_scan_capabilities_route(monkeypatch):
    class _FakeScanService:
        def get_scan_capabilities(self):
            return {"provider": "gemini", "available_google_keys": 4}

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)

    with TestClient(app) as client:
        response = client.get("/api/scans/capabilities")
        assert response.status_code == 200
        assert response.json()["provider"] == "gemini"
        assert response.json()["available_google_keys"] == 4


def test_scan_filename_diff_route(monkeypatch):
    class _FakeScanService:
        def compute_filename_diff(self, *, user_id, filenames):
            assert user_id == 7
            assert filenames == ["a.png", "b.png", "c.png"]
            return {
                "requested_total": 3,
                "already_scanned_count": 2,
                "to_scan_count": 1,
                "already_scanned_filenames": ["a.png", "b.png"],
                "to_scan_filenames": ["c.png"],
            }

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)
    with TestClient(app) as client:
        response = client.post(
            "/api/scans/filename-diff",
            json={"user_id": 7, "filenames": ["a.png", "b.png", "c.png"]},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["already_scanned_count"] == 2
        assert payload["to_scan_filenames"] == ["c.png"]


def test_scan_check_local_path_route(monkeypatch):
    class _FakeScanService:
        def check_local_scan_path(self, folder_path):
            assert folder_path == "/srv/data/BangStats/user/screens"
            return {"is_local": True, "canonical_path": "/srv/data/BangStats/user/screens"}

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)
    with TestClient(app) as client:
        response = client.post(
            "/api/scans/check-local-path",
            json={"folder_path": "/srv/data/BangStats/user/screens"},
        )
        assert response.status_code == 200
        assert response.json()["is_local"] is True


def test_scan_local_folder_route(monkeypatch):
    class _FakeScanService:
        def scan_local_folder(
            self,
            *,
            user_id,
            folder_path,
            filenames,
            parallel_workers,
            keys_per_worker,
        ):
            assert user_id == 7
            assert folder_path == "/srv/data/BangStats/user/screens"
            assert filenames == ["a.png", "b.png"]
            assert parallel_workers == 2
            assert keys_per_worker == 1
            return {
                "total_scanned": 2,
                "successful": 2,
                "errors": {},
                "error_files": {},
                "validated": 2,
                "persisted": 2,
                "failed_to_persist": 0,
                "skipped_duplicates": 0,
                "error_rate": 0.0,
                "additional": {"provider": "gemini"},
            }

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)
    with TestClient(app) as client:
        response = client.post(
            "/api/scans/scan-local-folder",
            json={
                "user_id": 7,
                "folder_path": "/srv/data/BangStats/user/screens",
                "filenames": ["a.png", "b.png"],
                "parallel_workers": 2,
                "keys_per_worker": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["total_scanned"] == 2


def test_scan_route_accepts_parallel_form_options(monkeypatch):
    class _FakeScanService:
        def scan_images(
            self,
            *,
            images_folder,
            image_list,
            user_id,
            persist_to_db,
            parallel_workers,
            keys_per_worker,
        ):
            assert user_id == 7
            assert persist_to_db is True
            assert parallel_workers == 2
            assert keys_per_worker == 2
            assert image_list == ["Screenshot_1.png"]
            return {
                "total_scanned": 1,
                "successful": 1,
                "errors": {
                    "note_errors": 0,
                    "not_found_errors": 0,
                    "fast_slow_errors": 0,
                    "max_combo_errors": 0,
                    "live_errors": 0,
                    "validation_errors": 0,
                },
                "error_files": {},
                "validated": 1,
                "persisted": 1,
                "failed_to_persist": 0,
                "skipped_duplicates": 0,
                "error_rate": 0.0,
                "additional": {
                    "provider": "gemini",
                    "parallel_enabled": True,
                    "mode": "2x2",
                },
            }

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)

    with TestClient(app) as client:
        response = client.post(
            "/api/scans",
            data={"user_id": "7", "parallel_workers": "2", "keys_per_worker": "2"},
            files={"files": ("Screenshot_1.png", io.BytesIO(b"fake"), "image/png")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["successful"] == 1
        assert payload["additional"]["mode"] == "2x2"


def test_scan_route_rejects_invalid_parallel_mode(monkeypatch):
    class _FakeScanService:
        def scan_images(self, **kwargs):
            raise ValueError("Requested 8 keys but only 4 keys available.")

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)

    with TestClient(app) as client:
        response = client.post(
            "/api/scans",
            data={"user_id": "7", "parallel_workers": "4", "keys_per_worker": "2"},
            files={"files": ("Screenshot_1.png", io.BytesIO(b"fake"), "image/png")},
        )
        assert response.status_code == 400


def test_create_sync_job_route(monkeypatch):
    created_job = SimpleNamespace(
        id=42,
        server="en",
        status="queued",
        requested_by_user_id=7,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
        songs=None,
        events=None,
        bands=None,
        error_message=None,
    )
    run_calls: list[tuple[int, str]] = []

    class _FakeSyncJobService:
        def create_job(self, *, server, requested_by_user_id):
            assert server == "en"
            assert requested_by_user_id == 7
            return created_job

    def _fake_run_sync_job(job_id: int, server: str):
        run_calls.append((job_id, server))

    monkeypatch.setattr(sync_router, "SyncJobService", _FakeSyncJobService)
    monkeypatch.setattr(sync_router, "_run_sync_job", _fake_run_sync_job)

    with TestClient(app) as client:
        response = client.post(
            "/api/sync/jobs",
            json={"server": "en", "requested_by_user_id": 7},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == 42
        assert payload["status"] == "queued"
        assert run_calls == [(42, "en")]


def test_create_sync_job_route_rejects_active_job(monkeypatch):
    class _FakeSyncJobService:
        def create_job(self, *, server, requested_by_user_id):
            raise ValueError("Sync already active (job_id=99, status=running)")

    monkeypatch.setattr(sync_router, "SyncJobService", _FakeSyncJobService)

    with TestClient(app) as client:
        response = client.post("/api/sync/jobs", json={"server": "en"})
        assert response.status_code == 409
        assert "already active" in response.json()["detail"].lower()


def test_sync_job_get_and_list_routes(monkeypatch):
    now = datetime.now(timezone.utc)
    job_a = SimpleNamespace(
        id=5,
        server="jp",
        status="running",
        requested_by_user_id=2,
        created_at=now,
        started_at=now,
        finished_at=None,
        songs=None,
        events=None,
        bands=None,
        error_message=None,
    )
    job_b = SimpleNamespace(
        id=4,
        server="en",
        status="succeeded",
        requested_by_user_id=2,
        created_at=now,
        started_at=now,
        finished_at=now,
        songs=700,
        events=420,
        bands=45,
        error_message=None,
    )

    class _FakeSyncJobService:
        def get_job(self, job_id):
            return job_a if job_id == 5 else None

        def list_jobs(self, *, limit, status):
            assert limit == 10
            assert status == "running"
            return [job_a, job_b]

    monkeypatch.setattr(sync_router, "SyncJobService", _FakeSyncJobService)

    with TestClient(app) as client:
        get_response = client.get("/api/sync/jobs/5")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == 5

        missing_response = client.get("/api/sync/jobs/999")
        assert missing_response.status_code == 404

        list_response = client.get("/api/sync/jobs", params={"limit": 10, "status": "running"})
        assert list_response.status_code == 200
        payload = list_response.json()
        assert len(payload["jobs"]) == 2
        assert payload["jobs"][0]["id"] == 5


def test_sync_jobs_list_route_rejects_invalid_status(monkeypatch):
    class _FakeSyncJobService:
        def list_jobs(self, *, limit, status):
            raise ValueError("invalid status 'abc'")

    monkeypatch.setattr(sync_router, "SyncJobService", _FakeSyncJobService)

    with TestClient(app) as client:
        response = client.get("/api/sync/jobs", params={"status": "abc"})
        assert response.status_code == 400


def test_run_sync_job_marks_success(monkeypatch):
    calls: list[tuple] = []

    class _FakeSyncJobService:
        def mark_running(self, job_id):
            calls.append(("running", job_id))

        def mark_succeeded(self, job_id, *, songs, events, bands):
            calls.append(("succeeded", job_id, songs, events, bands))

        def mark_failed(self, job_id, *, error_message):
            calls.append(("failed", job_id, error_message))

    monkeypatch.setattr(sync_router, "SyncJobService", _FakeSyncJobService)
    monkeypatch.setattr(sync_router, "update_db", lambda server: (111, 222, 333))

    sync_router._run_sync_job(1, "en")
    assert calls == [("running", 1), ("succeeded", 1, 111, 222, 333)]


def test_run_sync_job_marks_failure(monkeypatch):
    calls: list[tuple] = []

    class _FakeSyncJobService:
        def mark_running(self, job_id):
            calls.append(("running", job_id))

        def mark_succeeded(self, job_id, *, songs, events, bands):
            calls.append(("succeeded", job_id, songs, events, bands))

        def mark_failed(self, job_id, *, error_message):
            calls.append(("failed", job_id, error_message))

    def _raise(_server):
        raise RuntimeError("boom")

    monkeypatch.setattr(sync_router, "SyncJobService", _FakeSyncJobService)
    monkeypatch.setattr(sync_router, "update_db", _raise)

    sync_router._run_sync_job(2, "jp")
    assert calls[0] == ("running", 2)
    assert calls[1][0] == "failed"
    assert calls[1][1] == 2
    assert "boom" in calls[1][2]

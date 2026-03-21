from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bangstats_server.app import app
from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import webui as webui_router


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


def test_list_screenshots_includes_image_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    image_path = tmp_path / "shot.png"
    image_path.write_bytes(b"fake-image")

    monkeypatch.setattr(
        webui_router.SongService,
        "get_all_songs",
        lambda self: [
            SimpleNamespace(
                internal_song_id=99,
                name={"en": "A Song"},
                published_at={"en": 1},
            )
        ],
    )
    monkeypatch.setattr(
        webui_router.ScreenshotService,
        "get_screenshots_by_user",
        lambda self, user_id: [
            SimpleNamespace(
                id=1,
                user_id=user_id,
                filename="shot.png",
                song_id=99,
                difficulty="expert",
                live_type="free live",
                score=123456,
                full_combo=True,
                all_perfect=False,
                anomaly=False,
                timestamp=datetime(2026, 3, 19, 12, 0, 0),
            )
        ],
    )
    monkeypatch.setattr(webui_router.UploadStorageService, "resolve_user_file", lambda self, user_id, filename: None)
    monkeypatch.setattr(webui_router.ScanService, "find_success_image_path", lambda self, filename: image_path)

    with TestClient(app) as client:
        response = client.get("/api/users/7/screenshots")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["song_name"] == "A Song"
    assert payload["items"][0]["image_available"] is True
    assert payload["items"][0]["image_url"].endswith("/api/users/7/screenshots/1/image")


def test_get_screenshot_image_serves_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    image_path = tmp_path / "upload.png"
    image_path.write_bytes(b"\x89PNG\r\n")

    monkeypatch.setattr(
        webui_router.ScreenshotService,
        "get_screenshot_by_id",
        lambda self, screenshot_id: SimpleNamespace(
            id=screenshot_id,
            user_id=7,
            filename="upload.png",
        ),
    )
    monkeypatch.setattr(
        webui_router.UploadStorageService,
        "resolve_user_file",
        lambda self, user_id, filename: image_path,
    )

    with TestClient(app) as client:
        response = client.get("/api/users/7/screenshots/11/image")

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n"


def test_get_screenshot_image_thumb_variant_returns_jpeg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from PIL import Image

    image_path = tmp_path / "large.png"
    Image.new("RGB", (400, 300), color=(10, 120, 200)).save(image_path, format="PNG")

    monkeypatch.setattr(
        webui_router.ScreenshotService,
        "get_screenshot_by_id",
        lambda self, screenshot_id: SimpleNamespace(
            id=screenshot_id,
            user_id=7,
            filename="large.png",
        ),
    )
    monkeypatch.setattr(
        webui_router.UploadStorageService,
        "resolve_user_file",
        lambda self, user_id, filename: image_path,
    )

    with TestClient(app) as client:
        response = client.get("/api/users/7/screenshots/11/image", params={"variant": "thumb"})

    assert response.status_code == 200
    assert response.content.startswith(b"\xff\xd8")
    assert len(response.content) < image_path.stat().st_size


def test_get_screenshot_image_invalid_variant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    image_path = tmp_path / "x.png"
    image_path.write_bytes(b"\x89PNG\r\n")

    monkeypatch.setattr(
        webui_router.ScreenshotService,
        "get_screenshot_by_id",
        lambda self, screenshot_id: SimpleNamespace(
            id=screenshot_id,
            user_id=7,
            filename="x.png",
        ),
    )
    monkeypatch.setattr(
        webui_router.UploadStorageService,
        "resolve_user_file",
        lambda self, user_id, filename: image_path,
    )

    with TestClient(app) as client:
        response = client.get("/api/users/7/screenshots/11/image", params={"variant": "huge"})

    assert response.status_code == 400


def test_meta_song_config_and_export_import_routes(monkeypatch: pytest.MonkeyPatch):
    fake_user = SimpleNamespace(
        id=7,
        username="test",
        game_id="gid",
        server="en",
        screenshots_source="local",
        screenshots_path="/tmp/screens",
        server_folder_authorized=True,
        sync_command="sync",
        excluded_song_ids=[777],
    )

    monkeypatch.setattr(webui_router, "META_SONG_IDS", [111, 222])
    monkeypatch.setattr(webui_router.UserService, "get_user_by_id", lambda self, user_id: fake_user)
    monkeypatch.setattr(webui_router.UserService, "update_user", lambda self, user_id, payload: fake_user)
    monkeypatch.setattr(
        webui_router.ScreenshotService,
        "get_screenshots_by_user",
        lambda self, user_id: [
            SimpleNamespace(
                id=1,
                user_id=user_id,
                filename="shot.png",
                song_id=99,
                difficulty="expert",
                live_type="free live",
                score=123456,
                perfect=100,
                great=0,
                good=0,
                bad=0,
                miss=0,
                full_combo=True,
                all_perfect=False,
                anomaly=False,
                timestamp=datetime(2026, 3, 19, 12, 0, 0),
            )
        ],
    )
    monkeypatch.setattr(webui_router.ScreenshotService, "get_existing_filenames_for_user", lambda self, user_id, filenames: [])
    monkeypatch.setattr(webui_router.ScreenshotService, "create_screenshot", lambda self, screenshot_data: SimpleNamespace(id=2, **screenshot_data))
    monkeypatch.setattr(webui_router.UploadStorageService, "resolve_user_file", lambda self, user_id, filename: None)
    monkeypatch.setattr(webui_router.ScanService, "find_success_image_path", lambda self, filename: None)

    with TestClient(app) as client:
        meta = client.get("/api/users/7/meta-song-config")
        exported = client.get("/api/users/7/export")
        imported = client.post(
            "/api/users/7/import",
            json={
                "payload": {
                    "user": {"excluded_song_ids": [111, 777]},
                    "screenshots": [
                        {
                            "filename": "restored.png",
                            "song_id": 50,
                            "difficulty": "expert",
                            "live_type": "free live",
                            "score": 100000,
                            "perfect": 100,
                            "great": 0,
                            "good": 0,
                            "bad": 0,
                            "miss": 0,
                            "max_combo": 100,
                            "full_combo": False,
                            "all_perfect": False,
                        }
                    ],
                    "screenshot_references": [{"filename": "missing.png"}],
                }
            },
        )

    assert meta.status_code == 200
    assert meta.json()["effective_song_ids"] == [111, 222, 777]
    assert exported.status_code == 200
    assert exported.json()["meta_song_config"]["user_excluded_song_ids"] == [777]
    assert imported.status_code == 200
    assert imported.json()["restored_screenshots"] == 1
    assert imported.json()["unresolved_screenshot_references"] == ["missing.png"]


def test_dashboard_includes_current_event_diagnostics(monkeypatch: pytest.MonkeyPatch):
    fake_user = SimpleNamespace(
        id=7,
        username="test",
        game_id="gid",
        server="en",
        screenshots_source="local",
        screenshots_path="/tmp/screens",
        server_folder_authorized=True,
        sync_command="sync",
        excluded_song_ids=[],
    )
    monkeypatch.setattr(webui_router.UserService, "get_user_by_id", lambda self, user_id: fake_user)
    monkeypatch.setattr(webui_router.SongService, "get_all_songs", lambda self: [])
    monkeypatch.setattr(webui_router.ScreenshotService, "get_screenshots_by_user", lambda self, user_id: [])
    monkeypatch.setattr(webui_router.EventService, "get_current_event", lambda self, language="en": None)
    monkeypatch.setattr(webui_router.ScanJobService, "list_jobs_for_user", lambda self, user_id, limit, status=None: [])
    monkeypatch.setattr(webui_router.SyncJobService, "list_jobs", lambda self, limit, status=None: [])
    monkeypatch.setattr(webui_router.UploadStorageService, "get_usage", lambda self, user_id: {"file_count": 0, "total_size_mb": 0.0, "oldest_file_age_days": 0.0})
    monkeypatch.setattr(webui_router, "get_db_counts", lambda: (1, 2, 3))
    monkeypatch.setattr(webui_router.ScanService, "list_error_files", lambda self: {"total": 0, "errors": {}, "error_files": {}})

    with TestClient(app) as client:
        response = client.get("/api/users/7/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_event"] is None
    assert "No event found for server en" in payload["current_event_status"]
    assert payload["runtime"]["db_path"].endswith("bangstats.db")


def test_list_screenshots_supports_song_query_sort_and_accuracy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        webui_router.SongService,
        "get_all_songs",
        lambda self: [
            SimpleNamespace(internal_song_id=1, name={"en": "Alpha Song"}, published_at={"en": 1}),
            SimpleNamespace(internal_song_id=2, name={"en": "Beta Track"}, published_at={"en": 1}),
        ],
    )
    monkeypatch.setattr(
        webui_router.ScreenshotService,
        "get_screenshots_by_user",
        lambda self, user_id: [
            SimpleNamespace(
                id=1,
                user_id=user_id,
                filename="one.png",
                song_id=1,
                difficulty="expert",
                live_type="free live",
                score=900000,
                perfect=90,
                great=10,
                good=0,
                bad=0,
                miss=0,
                full_combo=True,
                all_perfect=False,
                anomaly=False,
                timestamp=datetime(2026, 3, 19, 12, 0, 0),
            ),
            SimpleNamespace(
                id=2,
                user_id=user_id,
                filename="two.png",
                song_id=2,
                difficulty="expert",
                live_type="free live",
                score=910000,
                perfect=80,
                great=20,
                good=0,
                bad=0,
                miss=0,
                full_combo=False,
                all_perfect=False,
                anomaly=False,
                timestamp=datetime(2026, 3, 18, 12, 0, 0),
            ),
        ],
    )
    monkeypatch.setattr(webui_router.UploadStorageService, "resolve_user_file", lambda self, user_id, filename: None)
    monkeypatch.setattr(webui_router.ScanService, "find_success_image_path", lambda self, filename: None)

    with TestClient(app) as client:
        response = client.get(
            "/api/users/7/screenshots",
            params={"song_query": "song", "sort_by": "accuracy", "sort_order": "desc"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["song_name"] == "Alpha Song"
    assert payload["items"][0]["accuracy"] == 90.0

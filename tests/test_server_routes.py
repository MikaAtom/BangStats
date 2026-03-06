from __future__ import annotations

import sys
import uuid
import io
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server"
if str(SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(SERVER_PATH))

from bangstats_server.app import app
from bangstats_server.api.routers import scans as scans_router


def test_health_route():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


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


def test_import_json_folder_route(monkeypatch):
    class _FakeScanService:
        def import_json_folder(self, *, folder_path, user_id, persist_to_db):
            assert folder_path == "/tmp/legacy-json"
            assert user_id == 1
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
                "user_id": 1,
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
            assert user_id == 3
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
            data={"user_id": "3", "parallel_workers": "2", "keys_per_worker": "2"},
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
            data={"user_id": "3", "parallel_workers": "4", "keys_per_worker": "2"},
            files={"files": ("Screenshot_1.png", io.BytesIO(b"fake"), "image/png")},
        )
        assert response.status_code == 400

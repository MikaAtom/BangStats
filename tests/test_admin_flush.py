from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import admin as admin_router
from bangstats_server.app import app


def test_admin_flush_resets_db_engine_when_db_flushed(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test", role="admin")
    calls: dict[str, int] = {"reset": 0}

    def _fake_flush_with_backup(**_kwargs):
        return Path("/tmp/backups/1"), ["/tmp/backups/1/bangstats.db"], []

    def _fake_reset_db_engine():
        calls["reset"] += 1

    monkeypatch.setattr(admin_router, "flush_with_backup", _fake_flush_with_backup)
    monkeypatch.setattr(admin_router, "reset_db_engine", _fake_reset_db_engine)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/admin/flush",
                json={"remote_cache": False, "scan_cache": False, "db": True},
            )
        assert response.status_code == 200
        assert calls["reset"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_flush_does_not_reset_without_db_move(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test", role="admin")
    calls: dict[str, int] = {"reset": 0}

    def _fake_flush_with_backup(**_kwargs):
        return Path("/tmp/backups/1"), ["/tmp/backups/1/scan_data_cache"], []

    def _fake_reset_db_engine():
        calls["reset"] += 1

    monkeypatch.setattr(admin_router, "flush_with_backup", _fake_flush_with_backup)
    monkeypatch.setattr(admin_router, "reset_db_engine", _fake_reset_db_engine)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/admin/flush",
                json={"remote_cache": False, "scan_cache": True, "db": False},
            )
        assert response.status_code == 200
        assert calls["reset"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_flush_resets_for_custom_db_filename(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test", role="admin")
    calls: dict[str, int] = {"reset": 0}

    def _fake_flush_with_backup(**_kwargs):
        return Path("/tmp/backups/1"), ["/tmp/backups/1/bangstats_dev.db"], []

    def _fake_reset_db_engine():
        calls["reset"] += 1

    monkeypatch.setattr(admin_router, "flush_with_backup", _fake_flush_with_backup)
    monkeypatch.setattr(admin_router, "reset_db_engine", _fake_reset_db_engine)
    monkeypatch.setattr(admin_router, "DB_PATH", Path("storage/bangstats_dev.db"))

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/admin/flush",
                json={"remote_cache": False, "scan_cache": False, "db": True},
            )
        assert response.status_code == 200
        assert calls["reset"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_flush_requires_admin_role():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test", role="user")

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/admin/flush",
                json={"remote_cache": False, "scan_cache": False, "db": True},
            )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

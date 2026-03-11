from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import scans as scans_router
from bangstats_server.app import app


def _job(
    job_id: int,
    user_id: int = 7,
    status: str = "queued",
    source_type: str = "upload",
    folder_path: str | None = None,
    total_files: int = 2,
):
    return SimpleNamespace(
        id=job_id,
        user_id=user_id,
        status=status,
        source_type=source_type,
        folder_path=folder_path,
        cancelled=False,
        total_files=total_files,
        processed=0,
        successful=0,
        validated=0,
        persisted=0,
        failed_to_persist=0,
        skipped_duplicates=0,
        errors={},
        error_files={},
        parallel_workers=None,
        keys_per_worker=None,
        created_at=datetime.utcnow(),
        started_at=None,
        finished_at=None,
        error_message=None,
    )


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


def test_authorize_server_folder_route(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(scans_router, "SCAN_MASTER_KEY", "secret")

    class _UserService:
        def update_user(self, *_args, **_kwargs):
            return SimpleNamespace(server_folder_authorized=True)

    monkeypatch.setattr(scans_router, "UserService", _UserService)

    with TestClient(app) as client:
        bad = client.post("/api/scans/authorize-server-folder", json={"master_key": "wrong"})
        assert bad.status_code == 403

        ok = client.post("/api/scans/authorize-server-folder", json={"master_key": "secret"})
        assert ok.status_code == 200
        assert ok.json()["authorized"] is True


def test_check_local_path_whitelist(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(scans_router, "SCAN_SERVER_FOLDER_WHITELIST", [Path("/srv/data")])

    class _FakeScanService:
        def check_local_scan_path(self, folder_path):
            return {"is_local": True, "canonical_path": folder_path}

    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)
    with TestClient(app) as client:
        denied = client.post(
            "/api/scans/check-local-path",
            json={"user_id": 7, "folder_path": "/tmp/not-allowed"},
        )
        assert denied.status_code == 403

        allowed = client.post(
            "/api/scans/check-local-path",
            json={"user_id": 7, "folder_path": "/srv/data/screens"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["is_local"] is True


def test_scan_job_routes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    upload_dir = tmp_path / "uploads" / "7"
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "a.png").write_bytes(b"x")
    (upload_dir / "b.png").write_bytes(b"x")

    class _UploadStorageService:
        def ensure_user_dir(self, _user_id: int) -> Path:
            return upload_dir

    class _ScanJobService:
        jobs = {1: _job(1)}

        def create_job(self, **_kwargs):
            created = _job(2)
            self.jobs[2] = created
            return created

        def get_job(self, job_id: int):
            return self.jobs.get(job_id)

        def list_jobs_for_user(self, **_kwargs):
            return [self.jobs[1]]

        def request_cancel(self, job_id: int):
            job = self.jobs[job_id]
            job.cancelled = True
            return job

        def mark_cancelled(self, job_id: int, **_kwargs):
            job = self.jobs[job_id]
            job.status = "cancelled"
            job.cancelled = True
            return job

    monkeypatch.setattr(scans_router, "UploadStorageService", _UploadStorageService)
    monkeypatch.setattr(scans_router, "ScanJobService", _ScanJobService)
    monkeypatch.setattr(scans_router, "_run_scan_job", lambda **_kwargs: None)

    with TestClient(app) as client:
        created = client.post(
            "/api/scans/jobs",
            json={
                "user_id": 7,
                "source_type": "upload",
                "filenames": ["a.png", "b.png"],
            },
        )
        assert created.status_code == 200
        assert created.json()["id"] == 2

        listed = client.get("/api/scans/jobs", params={"limit": 10})
        assert listed.status_code == 200
        assert listed.json()["jobs"][0]["id"] == 1

        detail = client.get("/api/scans/jobs/1")
        assert detail.status_code == 200
        assert detail.json()["status"] == "queued"

        cancelled = client.post("/api/scans/jobs/1/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"


def test_check_local_path_accepts_dev_simulated_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    sim_root = tmp_path / "simulated_server_folders"
    canonical = sim_root / "user_7" / "server_folder"
    canonical.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(scans_router, "BANGSTATS_ENV", "dev")
    monkeypatch.setattr(scans_router, "DEV_SIMULATE_SCREENSHOT_LOCATIONS", True)
    monkeypatch.setattr(scans_router, "SCAN_SERVER_FOLDER_WHITELIST", [sim_root])

    class _FakeDevSimulationService:
        def resolve_server_folder_path(self, user_id: int, requested_path: str):
            assert user_id == 7
            assert requested_path == "simulated"
            return canonical

    class _FakeScanService:
        def check_local_scan_path(self, folder_path: str):
            assert folder_path == str(canonical)
            return {"is_local": True, "canonical_path": str(canonical)}

    monkeypatch.setattr(scans_router, "DevSimulationService", _FakeDevSimulationService)
    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)

    with TestClient(app) as client:
        response = client.post(
            "/api/scans/check-local-path",
            json={"user_id": 7, "folder_path": "simulated"},
        )
        assert response.status_code == 200
        assert response.json()["is_local"] is True
        assert response.json()["canonical_path"] == str(canonical)


def test_create_scan_job_server_folder_dev_simulated_non_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    sim_root = tmp_path / "simulated_server_folders"
    canonical = sim_root / "user_7" / "server_folder"
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "Screenshot_1.png").write_bytes(b"x")

    monkeypatch.setattr(scans_router, "BANGSTATS_ENV", "dev")
    monkeypatch.setattr(scans_router, "DEV_SIMULATE_SCREENSHOT_LOCATIONS", True)
    monkeypatch.setattr(scans_router, "SCAN_SERVER_FOLDER_WHITELIST", [sim_root])

    class _FakeDevSimulationService:
        def resolve_server_folder_path(self, user_id: int, requested_path: str):
            assert user_id == 7
            assert requested_path == "simulated"
            return canonical

    class _FakeScanService:
        def check_local_scan_path(self, folder_path: str):
            return {"is_local": True, "canonical_path": folder_path}

    class _ScanJobService:
        jobs = {1: _job(1)}

        def create_job(self, **kwargs):
            created = _job(
                3,
                user_id=int(kwargs.get("user_id", 7)),
                status="queued",
                source_type=str(kwargs.get("source_type", "server_folder")),
                folder_path=str(kwargs.get("folder_path")),
                total_files=int(kwargs.get("total_files", 0)),
            )
            self.jobs[3] = created
            return created

        def get_job(self, job_id: int):
            return self.jobs.get(job_id)

    monkeypatch.setattr(scans_router, "DevSimulationService", _FakeDevSimulationService)
    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)
    monkeypatch.setattr(scans_router, "ScanJobService", _ScanJobService)
    monkeypatch.setattr(scans_router, "_run_scan_job", lambda **_kwargs: None)

    with TestClient(app) as client:
        created = client.post(
            "/api/scans/jobs",
            json={
                "user_id": 7,
                "source_type": "server_folder",
                "folder_path": "simulated",
            },
        )
        assert created.status_code == 200
        payload = created.json()
        assert payload["id"] == 3
        assert payload["status"] == "queued"
        assert payload["source_type"] == "server_folder"
        assert payload["folder_path"] == str(canonical)
        assert payload["total_files"] == 1


def test_create_scan_job_server_folder_dev_simulated_empty_folder_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    sim_root = tmp_path / "simulated_server_folders"
    canonical = sim_root / "user_7" / "server_folder"
    canonical.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(scans_router, "BANGSTATS_ENV", "dev")
    monkeypatch.setattr(scans_router, "DEV_SIMULATE_SCREENSHOT_LOCATIONS", True)
    monkeypatch.setattr(scans_router, "SCAN_SERVER_FOLDER_WHITELIST", [sim_root])

    class _FakeDevSimulationService:
        def resolve_server_folder_path(self, user_id: int, requested_path: str):
            assert user_id == 7
            assert requested_path == "simulated"
            return canonical

    class _FakeScanService:
        def check_local_scan_path(self, folder_path: str):
            return {"is_local": True, "canonical_path": folder_path}

    class _ScanJobService:
        jobs = {1: _job(1)}

        def create_job(self, **kwargs):
            created = _job(
                4,
                user_id=int(kwargs.get("user_id", 7)),
                status="queued",
                source_type=str(kwargs.get("source_type", "server_folder")),
                folder_path=str(kwargs.get("folder_path")),
                total_files=int(kwargs.get("total_files", 0)),
            )
            self.jobs[4] = created
            return created

        def get_job(self, job_id: int):
            return self.jobs.get(job_id)

    monkeypatch.setattr(scans_router, "DevSimulationService", _FakeDevSimulationService)
    monkeypatch.setattr(scans_router, "ScanService", _FakeScanService)
    monkeypatch.setattr(scans_router, "ScanJobService", _ScanJobService)
    monkeypatch.setattr(scans_router, "_run_scan_job", lambda **_kwargs: None)

    with TestClient(app) as client:
        created = client.post(
            "/api/scans/jobs",
            json={
                "user_id": 7,
                "source_type": "server_folder",
                "folder_path": "simulated",
            },
        )
        assert created.status_code == 400
        assert "No files available for scan job" in created.json()["detail"]

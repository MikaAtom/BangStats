from pathlib import Path
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import dev as dev_router
from bangstats_server.core.services import dev_simulation as dev_simulation_module


def _build_dev_app() -> FastAPI:
    app = FastAPI()
    app.include_router(dev_router.router, prefix="/api", dependencies=[Depends(get_current_user)])
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7,
        username="dev_user",
        game_id="gid",
        server="en",
        server_folder_authorized=True,
    )
    return app


def _png_count(folder: Path) -> int:
    return len(list(folder.glob("*.png")))


def test_prepare_simulated_folders_local_clear_existing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dev_simulation_module, "BANGSTATS_ENV", "dev")
    monkeypatch.setattr(dev_simulation_module, "DEV_SIMULATE_SCREENSHOT_LOCATIONS", True)
    monkeypatch.setattr(
        dev_simulation_module,
        "DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT",
        tmp_path / "sim_local",
    )
    monkeypatch.setattr(
        dev_simulation_module,
        "DEV_SIMULATED_SERVER_FOLDER_ROOT",
        tmp_path / "sim_server",
    )

    local_folder = tmp_path / "sim_local" / "user_7" / "local_source"
    local_folder.mkdir(parents=True, exist_ok=True)
    existing = local_folder / "legacy.png"
    existing.write_bytes(b"x")

    app = _build_dev_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/dev/prepare-simulated-folders",
            json={
                "user_id": 7,
                "target": "local",
                "count": 5,
                "time_span_days": 12,
                "clear_existing": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["local_existing_before"] == 1
    assert payload["local_created"] == 5
    assert payload["server_path"] is None
    assert existing.exists() is False
    assert _png_count(local_folder) > 0
    assert payload["local_path"] == str(local_folder.resolve())


def test_prepare_simulated_folders_both_and_scope_validation(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dev_simulation_module, "BANGSTATS_ENV", "dev")
    monkeypatch.setattr(dev_simulation_module, "DEV_SIMULATE_SCREENSHOT_LOCATIONS", True)
    monkeypatch.setattr(
        dev_simulation_module,
        "DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT",
        tmp_path / "sim_local",
    )
    monkeypatch.setattr(
        dev_simulation_module,
        "DEV_SIMULATED_SERVER_FOLDER_ROOT",
        tmp_path / "sim_server",
    )

    app = _build_dev_app()
    with TestClient(app) as client:
        denied = client.post(
            "/api/dev/prepare-simulated-folders",
            json={
                "user_id": 9,
                "target": "both",
                "count": 2,
                "time_span_days": 30,
                "clear_existing": False,
            },
        )
        assert denied.status_code == 403

        response = client.post(
            "/api/dev/prepare-simulated-folders",
            json={
                "user_id": 7,
                "target": "both",
                "count": 2,
                "time_span_days": 30,
                "clear_existing": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["local_path"] is not None
    assert payload["server_path"] is not None
    assert payload["local_created"] == 2
    assert payload["server_created"] == 2


def test_prepare_simulated_folders_disabled_in_non_dev(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dev_simulation_module, "BANGSTATS_ENV", "production")
    monkeypatch.setattr(dev_simulation_module, "DEV_SIMULATE_SCREENSHOT_LOCATIONS", True)
    monkeypatch.setattr(
        dev_simulation_module,
        "DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT",
        tmp_path / "sim_local",
    )
    monkeypatch.setattr(
        dev_simulation_module,
        "DEV_SIMULATED_SERVER_FOLDER_ROOT",
        tmp_path / "sim_server",
    )

    app = _build_dev_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/dev/prepare-simulated-folders",
            json={"user_id": 7, "target": "local", "count": 1, "time_span_days": 1},
        )
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()

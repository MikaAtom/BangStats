from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server"
if str(SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(SERVER_PATH))

from bangstats_server.app import app


def test_health_route():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_user_crud_routes():
    client = TestClient(app)
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

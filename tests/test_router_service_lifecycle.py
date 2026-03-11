from types import SimpleNamespace

from fastapi.testclient import TestClient

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.app import app
from bangstats_server.api.routers import auth as auth_router
from bangstats_server.api.routers import users as users_router


def test_users_router_builds_service_per_request(monkeypatch):
    calls = {"count": 0}

    class _FakeUserService:
        def __init__(self):
            calls["count"] += 1

        def get_user_by_username(self, username: str):
            return SimpleNamespace(
                id=1,
                game_id="gid",
                username=username,
                server="en",
                screenshots_source="local",
                screenshots_path="",
                server_folder_authorized=False,
                sync_command=None,
            )

    monkeypatch.setattr(users_router, "UserService", _FakeUserService)

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        username="test",
        game_id="gid",
        server="en",
        server_folder_authorized=True,
    )
    try:
        with TestClient(app) as client:
            first = client.get("/api/users", params={"username": "a"})
            second = client.get("/api/users", params={"username": "b"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 2


def test_auth_router_builds_service_per_request(monkeypatch):
    calls = {"count": 0}

    class _FakeAuthService:
        def __init__(self, rate_limiter=None):
            _ = rate_limiter
            calls["count"] += 1

        def login(self, *, username: str, password: str, ip: str):
            _ = password
            _ = ip
            user = SimpleNamespace(
                id=1,
                game_id="gid",
                username=username,
                server="en",
                screenshots_source="local",
                screenshots_path="",
                server_folder_authorized=False,
                sync_command=None,
            )
            return user, "token-1"

        @staticmethod
        def logout(_token_value: str):
            return None

    monkeypatch.setattr(auth_router, "AuthService", _FakeAuthService)

    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "dev_user", "password": "pw"})
        logout = client.post("/api/auth/logout", headers={"Authorization": "Bearer token-1"})

    assert login.status_code == 200
    assert logout.status_code == 200
    assert calls["count"] == 2

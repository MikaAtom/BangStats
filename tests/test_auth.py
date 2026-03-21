from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from bangstats_server.api.routers import auth as auth_router
from bangstats_server.app import app
from bangstats_server.core.db.repositories.token_repository import TokenRepository
from bangstats_server.core.services.auth import AuthService, LoginRateLimiter
from bangstats_server.core.services.user import UserService


@pytest.fixture(autouse=True)
def _reset_auth_service(monkeypatch: pytest.MonkeyPatch):
    rate_limiter = LoginRateLimiter()
    monkeypatch.setattr(auth_router, "rate_limiter", rate_limiter)
    monkeypatch.setattr(
        auth_router,
        "auth_service",
        AuthService(rate_limiter=rate_limiter),
    )


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, username: str | None = None, game_id: str | None = None):
    resolved_username = username or f"user_{uuid4().hex[:10]}"
    resolved_game_id = game_id or f"gid_{uuid4().hex[:12]}"
    payload = {
        "username": resolved_username,
        "password": "secret123",
        "game_id": resolved_game_id,
        "server": "en",
    }
    response = client.post("/api/auth/register", json=payload)
    return response, payload


def test_register_happy_path(client: TestClient):
    response, payload = _register(client)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["token"], str) and body["token"]
    assert body["user"]["username"] == payload["username"]
    assert body["user"]["game_id"] == payload["game_id"]
    assert body["user"]["server"] == "en"


def test_register_duplicate_username_and_missing_fields(client: TestClient):
    response, payload = _register(client, username=f"user_{uuid4().hex[:8]}")
    assert response.status_code == 200

    duplicate_response = client.post(
        "/api/auth/register",
        json={
            "username": payload["username"],
            "password": "other",
            "game_id": f"gid_{uuid4().hex[:8]}",
            "server": "en",
        },
    )
    assert duplicate_response.status_code == 400
    assert "username already exists" in duplicate_response.json()["detail"]

    missing_field_response = client.post(
        "/api/auth/register",
        json={"username": "x", "game_id": "y", "server": "en"},
    )
    assert missing_field_response.status_code == 422


def test_login_happy_path_and_invalid_credentials(client: TestClient):
    _, payload = _register(client)

    ok_response = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert ok_response.status_code == 200
    assert ok_response.json()["user"]["username"] == payload["username"]

    wrong_password_response = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": "wrong"},
    )
    assert wrong_password_response.status_code == 401
    assert wrong_password_response.json()["detail"] == "Invalid username or password"

    nonexistent_response = client.post(
        "/api/auth/login",
        json={"username": f"missing_{uuid4().hex[:8]}", "password": "irrelevant"},
    )
    assert nonexistent_response.status_code == 401
    assert nonexistent_response.json()["detail"] == "Invalid username or password"


def test_legacy_user_can_set_password_and_then_login(client: TestClient):
    suffix = uuid4().hex[:8]
    username = f"legacy_{suffix}"
    game_id = f"gid_{suffix}"

    created = UserService().create_user(
        {
            "username": username,
            "game_id": game_id,
            "server": "en",
        }
    )
    assert created.username == username

    blocked_login = client.post(
        "/api/auth/login",
        json={"username": username, "password": "new-secret"},
    )
    assert blocked_login.status_code == 403
    assert "password setup" in blocked_login.json()["detail"].lower()

    setup_response = client.post(
        "/api/auth/legacy-password-setup",
        json={
            "username": username,
            "game_id": game_id,
            "password": "new-secret",
        },
    )
    assert setup_response.status_code == 200
    assert setup_response.json()["user"]["username"] == username

    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "new-secret"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["user"]["username"] == username


def test_legacy_user_can_use_temporary_legacy_login(client: TestClient):
    suffix = uuid4().hex[:8]
    username = f"legacy_temp_{suffix}"
    game_id = f"gid_{suffix}"

    created = UserService().create_user(
        {
            "username": username,
            "game_id": game_id,
            "server": "en",
        }
    )
    assert created.username == username

    login_response = client.post(
        "/api/auth/legacy-login",
        json={"username": username, "game_id": game_id},
    )
    assert login_response.status_code == 200
    assert login_response.json()["user"]["username"] == username

    bad_response = client.post(
        "/api/auth/legacy-login",
        json={"username": username, "game_id": "wrong"},
    )
    assert bad_response.status_code == 401


def test_logout_happy_path_and_already_logged_out_token(client: TestClient):
    register_response, _ = _register(client)
    token = register_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/api/auth/logout", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "ok"

    second = client.post("/api/auth/logout", headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "ok"


def test_protected_route_requires_valid_token_and_rejects_expired_token(client: TestClient):
    register_response, _ = _register(client)
    user = register_response.json()["user"]
    user_id = int(user["id"])

    no_token = client.get(f"/api/users/{user_id}")
    assert no_token.status_code == 401

    expired_token_value = f"expired_{uuid4().hex}"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    with TokenRepository() as repo:
        repo.create(token=expired_token_value, user_id=user_id, expires_at=expires_at)

    expired = client.get(
        f"/api/users/{user_id}",
        headers={"Authorization": f"Bearer {expired_token_value}"},
    )
    assert expired.status_code == 401
    assert expired.json()["detail"] == "Invalid or expired token"


def test_login_rate_limiting_returns_429_after_five_failures(client: TestClient):
    _, payload = _register(client)

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": payload["username"], "password": "wrong"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/login",
        json={"username": payload["username"], "password": "wrong"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many login attempts"


def test_issue_token_retries_on_sqlite_readonly(monkeypatch: pytest.MonkeyPatch):
    rate_limiter = LoginRateLimiter()
    service = AuthService(rate_limiter=rate_limiter)

    calls = {"create": 0, "reset": 0}

    class _Repo:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def delete_expired(self, *, now):
            return 0

        def create(self, *, token, user_id, expires_at):
            calls["create"] += 1
            if calls["create"] == 1:
                raise OperationalError("INSERT", {}, sqlite3.OperationalError("attempt to write a readonly database"))
            return None

    def _reset_engine():
        calls["reset"] += 1

    monkeypatch.setattr("bangstats_server.core.services.auth.TokenRepository", _Repo)
    monkeypatch.setattr("bangstats_server.core.services.auth.reset_db_engine", _reset_engine)

    token = service.issue_token(user_id=1)

    assert isinstance(token, str) and token
    assert calls["create"] == 2
    assert calls["reset"] == 1

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import reference as reference_router
from bangstats_server.app import app


class _FakeReferenceService:
    def __init__(self, items: list[dict]):
        self._items = items

    def list_since_id(self, since_id: int, limit: int = 5000) -> list[dict]:
        return [item for item in self._items if int(item["id"]) > since_id][:limit]

    def get_all(self) -> list[dict]:
        return list(self._items)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        username=f"u_{uuid4().hex[:6]}",
        game_id=f"g_{uuid4().hex[:6]}",
        server="en",
    )

    songs = [{"id": 1, "internal_song_id": 101}, {"id": 6, "internal_song_id": 106}]
    events = [{"id": 2, "event_id": 2001}, {"id": 7, "event_id": 2002}]
    bands = [{"id": 3, "internal_band_id": 3001}, {"id": 8, "internal_band_id": 3002}]

    song_service = _FakeReferenceService(songs)
    event_service = _FakeReferenceService(events)
    band_service = _FakeReferenceService(bands)

    monkeypatch.setattr(
        reference_router,
        "song_service",
        SimpleNamespace(
            list_songs_since_id=song_service.list_since_id,
            get_all_songs=song_service.get_all,
        ),
    )
    monkeypatch.setattr(
        reference_router,
        "event_service",
        SimpleNamespace(
            list_events_since_id=event_service.list_since_id,
            get_all_events=event_service.get_all,
        ),
    )
    monkeypatch.setattr(
        reference_router,
        "band_service",
        SimpleNamespace(
            list_bands_since_id=band_service.list_since_id,
            get_all_bands=band_service.get_all,
        ),
    )

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


def test_reference_songs_since_id(client: TestClient):
    all_response = client.get("/api/reference/songs", params={"since_id": 0})
    assert all_response.status_code == 200
    all_payload = all_response.json()
    assert [item["id"] for item in all_payload["items"]] == [1, 6]
    assert all_payload["max_id"] == 6

    newer_response = client.get("/api/reference/songs", params={"since_id": 5})
    assert newer_response.status_code == 200
    newer_payload = newer_response.json()
    assert [item["id"] for item in newer_payload["items"]] == [6]
    assert newer_payload["max_id"] == 6


def test_reference_events_bands_since_id_and_counts(client: TestClient):
    events_response = client.get("/api/reference/events", params={"since_id": 0})
    assert events_response.status_code == 200
    assert [item["id"] for item in events_response.json()["items"]] == [2, 7]

    bands_response = client.get("/api/reference/bands", params={"since_id": 4})
    assert bands_response.status_code == 200
    assert [item["id"] for item in bands_response.json()["items"]] == [8]

    counts_response = client.get("/api/reference/counts")
    assert counts_response.status_code == 200
    assert counts_response.json() == {"songs": 2, "events": 2, "bands": 2}

import json
from pathlib import Path

import pytest

from bangstats_server.core.adapters import fake_remote
from bangstats_server.core.adapters.fake_remote import FakeRemoteDataService


@pytest.fixture
def seed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    package_root = tmp_path / "core"
    adapter_dir = package_root / "adapters"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    seed = adapter_dir / "seed_data.json"
    seed.write_text(
        json.dumps(
            {
                "songs": [
                    {"internal_song_id": 100, "published_at": {"en": "1", "jp": "1"}},
                    {"internal_song_id": 101, "published_at": {"en": None, "jp": "1"}},
                ],
                "events": [
                    {"event_id": 200, "event_end_at": {"en": "2", "jp": "2"}},
                    {"event_id": 201, "event_end_at": {"en": None, "jp": "2"}},
                ],
                "bands": [
                    {"internal_band_id": 300, "name": {"en": "Band", "jp": "バンド"}},
                    {"internal_band_id": 301, "name": {"jp": "のみJP"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fake_remote, "PACKAGE_ROOT", package_root)
    return seed


def test_fake_remote_server_filtering(seed_file: Path):
    _ = seed_file
    service_en = FakeRemoteDataService(server="en")
    service_jp = FakeRemoteDataService(server="jp")

    assert service_en.get_songs_ids() == [100]
    assert sorted(service_jp.get_songs_ids()) == [100, 101]

    events_en = service_en.get_events_info()
    events_jp = service_jp.get_events_info()
    assert sorted(events_en.keys()) == ["200"]
    assert sorted(events_jp.keys()) == ["200", "201"]

    bands_en = service_en.get_bands_info()
    bands_jp = service_jp.get_bands_info()
    assert sorted(bands_en.keys()) == ["300"]
    assert sorted(bands_jp.keys()) == ["300", "301"]


def test_fake_remote_song_lookup(seed_file: Path):
    _ = seed_file
    service = FakeRemoteDataService(server="jp")
    song = service.get_song_info(101)
    assert song is not None
    assert int(song["internal_song_id"]) == 101

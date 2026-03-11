from pathlib import Path

from bangstats_cli import cache


class _FakeReferenceAPI:
    def __init__(self):
        self.song_calls: list[tuple[int, int]] = []
        self.event_calls: list[tuple[int, int]] = []
        self.band_calls: list[tuple[int, int]] = []

    def get_reference_counts(self):
        return {"songs": 3, "events": 2, "bands": 1}

    def get_reference_songs(self, since_id: int = 0, limit: int = 5000):
        self.song_calls.append((since_id, limit))
        if since_id < 2:
            return {"items": [{"id": 2, "internal_song_id": 102}, {"id": 3, "internal_song_id": 103}]}
        return {"items": []}

    def get_reference_events(self, since_id: int = 0, limit: int = 5000):
        self.event_calls.append((since_id, limit))
        if since_id == 0:
            return {"items": [{"id": 1, "event_id": 2001}, {"id": 2, "event_id": 2002}]}
        return {"items": []}

    def get_reference_bands(self, since_id: int = 0, limit: int = 5000):
        self.band_calls.append((since_id, limit))
        if since_id == 0:
            return {"items": [{"id": 1, "internal_band_id": 3001}]}
        return {"items": []}


def test_read_write_cache_round_trip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    payload = {"max_id": 7, "data": {"7": {"id": 7, "x": 1}}}
    cache._write_cache("songs", payload)
    loaded = cache._read_cache("songs")
    assert loaded == payload


def test_merge_items_updates_data_and_max_id():
    payload = {"max_id": 1, "data": {"1": {"id": 1, "v": "old"}}}
    cache._merge_items(
        payload,
        [{"id": 2, "v": "new"}, {"id": 0, "v": "ignored"}, {"id": 1, "v": "updated"}],
    )
    assert payload["max_id"] == 2
    assert payload["data"]["1"]["v"] == "updated"
    assert payload["data"]["2"]["v"] == "new"
    assert "0" not in payload["data"]


def test_sync_reference_cache_incremental(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    monkeypatch.setattr(cache, "CACHE_LIMIT", 2)

    # Existing local cache has one song, so sync should fetch only newer records.
    cache._write_cache("songs", {"max_id": 1, "data": {"1": {"id": 1, "internal_song_id": 101}}})
    api = _FakeReferenceAPI()

    result = cache.sync_reference_cache(api)

    assert sorted(result["songs"]["data"].keys()) == ["1", "2", "3"]
    assert result["songs"]["max_id"] == 3
    assert len(result["events"]["data"]) == 2
    assert len(result["bands"]["data"]) == 1
    assert api.song_calls[0][0] == 1


def test_resolve_song_name_fallback_chain():
    song_cache = {
        "data": {
            "1": {"id": 1, "name": {"jp": "JP Name", "en": "EN Name"}},
            "2": {"id": 2, "name": {"en": "English Only"}},
            "3": {"id": 3, "name": {"kr": "Any Name"}},
            "4": {"id": 4, "name": {}},
        }
    }

    assert cache.resolve_song_name(song_cache, 1, server="jp") == "JP Name"
    assert cache.resolve_song_name(song_cache, 2, server="cn") == "English Only"
    assert cache.resolve_song_name(song_cache, 3, server="tw") == "Any Name"
    assert cache.resolve_song_name(song_cache, 4, server="en") == "Song 4"
    assert cache.resolve_song_name(song_cache, 999, server="en") == "Song 999"


def test_search_songs_case_insensitive_and_limit():
    song_cache = {
        "data": {
            "11": {"id": 11, "internal_song_id": 1001, "name": {"en": "Blue Song"}},
            "12": {"id": 12, "internal_song_id": 1002, "name": {"en": "BLOOM Dream"}},
            "13": {"id": 13, "internal_song_id": 1003, "name": {"en": "Other"}},
        }
    }

    results = cache.search_songs(song_cache, query="bl", server="en", limit=1)
    assert len(results) == 1
    assert results[0]["song_id"] in {1001, 1002}

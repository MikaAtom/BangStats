import json
from pathlib import Path
from typing import Any

from bangstats_cli.api_client import BangStatsAPI

CACHE_ROOT = Path.home() / ".bangstats" / "cache"
CACHE_LIMIT = 5000
SERVER_KEYS = ("en", "jp", "tw", "cn", "kr")


def _cache_file(name: str) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{name}.json"


def _read_cache(name: str) -> dict[str, Any]:
    path = _cache_file(name)
    if not path.exists():
        return {"max_id": 0, "data": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"max_id": 0, "data": {}}
    if not isinstance(payload, dict):
        return {"max_id": 0, "data": {}}
    payload.setdefault("max_id", 0)
    payload.setdefault("data", {})
    if not isinstance(payload["data"], dict):
        payload["data"] = {}
    return payload


def _write_cache(name: str, payload: dict[str, Any]) -> None:
    path = _cache_file(name)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _merge_items(payload: dict[str, Any], items: list[dict[str, Any]]) -> None:
    data = payload.setdefault("data", {})
    max_id = int(payload.get("max_id", 0) or 0)
    for item in items:
        item_id = int(item.get("id", 0) or 0)
        if item_id <= 0:
            continue
        data[str(item_id)] = item
        if item_id > max_id:
            max_id = item_id
    payload["max_id"] = max_id


def _sync_one(api: BangStatsAPI, name: str, getter) -> dict[str, Any]:
    payload = _read_cache(name)
    since_id = int(payload.get("max_id", 0) or 0)
    while True:
        chunk = getter(since_id=since_id, limit=CACHE_LIMIT)
        items = chunk.get("items", [])
        if not isinstance(items, list) or not items:
            break
        _merge_items(payload, [item for item in items if isinstance(item, dict)])
        since_id = int(payload.get("max_id", since_id) or since_id)
        if len(items) < CACHE_LIMIT:
            break
    _write_cache(name, payload)
    return payload


def sync_reference_cache(api: BangStatsAPI) -> dict[str, dict[str, Any]]:
    counts = api.get_reference_counts()
    songs_cache = _read_cache("songs")
    events_cache = _read_cache("events")
    bands_cache = _read_cache("bands")

    if int(counts.get("songs", 0) or 0) > len(songs_cache.get("data", {})):
        songs_cache = _sync_one(api, "songs", api.get_reference_songs)
    if int(counts.get("events", 0) or 0) > len(events_cache.get("data", {})):
        events_cache = _sync_one(api, "events", api.get_reference_events)
    if int(counts.get("bands", 0) or 0) > len(bands_cache.get("data", {})):
        bands_cache = _sync_one(api, "bands", api.get_reference_bands)

    return {"songs": songs_cache, "events": events_cache, "bands": bands_cache}


def resolve_song_name(song_cache: dict[str, Any], song_id: int, server: str = "en") -> str:
    song = song_cache.get("data", {}).get(str(song_id))
    if not isinstance(song, dict):
        return f"Song {song_id}"
    name = song.get("name")
    if not isinstance(name, dict):
        return f"Song {song_id}"
    preferred = name.get(server) or name.get("en")
    if preferred:
        return str(preferred)
    for key in SERVER_KEYS:
        value = name.get(key)
        if value:
            return str(value)
    return f"Song {song_id}"


def search_songs(song_cache: dict[str, Any], query: str, server: str = "en", limit: int = 20) -> list[dict[str, Any]]:
    needle = query.strip().casefold()
    if not needle:
        return []
    results: list[dict[str, Any]] = []
    for item in song_cache.get("data", {}).values():
        if not isinstance(item, dict):
            continue
        song_id = int(item.get("internal_song_id", 0) or 0)
        if song_id <= 0:
            continue
        song_name = resolve_song_name(song_cache, int(item.get("id", 0) or 0), server)
        if needle in song_name.casefold():
            results.append({"song_id": song_id, "song_name": song_name})
    results.sort(key=lambda row: row["song_name"].casefold())
    return results[:limit]

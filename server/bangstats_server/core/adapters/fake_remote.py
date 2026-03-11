import json
from pathlib import Path
from typing import Any

from bangstats_server.core.config import PACKAGE_ROOT


class FakeRemoteDataService:
    returns_organized_payloads = True

    def __init__(self, server: str):
        self.server = server
        self._seed_path = PACKAGE_ROOT / "adapters" / "seed_data.json"
        self._payload = self._load_payload()

    def _load_payload(self) -> dict[str, Any]:
        if not self._seed_path.exists():
            return {"songs": [], "events": [], "bands": []}
        try:
            return json.loads(self._seed_path.read_text(encoding="utf-8"))
        except Exception:
            return {"songs": [], "events": [], "bands": []}

    def _song_available(self, song: dict[str, Any]) -> bool:
        published_at = song.get("published_at")
        if not isinstance(published_at, dict):
            return True
        value = published_at.get(self.server)
        return value is not None and value != ""

    def _event_available(self, event: dict[str, Any]) -> bool:
        end_at = event.get("event_end_at")
        if not isinstance(end_at, dict):
            return True
        value = end_at.get(self.server)
        return value is not None and value != ""

    def _band_available(self, band: dict[str, Any]) -> bool:
        name = band.get("name")
        if not isinstance(name, dict):
            return True
        value = name.get(self.server)
        return value is not None and value != ""

    def get_songs_ids(self) -> list[int]:
        songs = self._payload.get("songs", [])
        result: list[int] = []
        for song in songs:
            if not isinstance(song, dict) or not self._song_available(song):
                continue
            try:
                result.append(int(song.get("internal_song_id", 0)))
            except Exception:
                continue
        return result

    def get_song_info(self, song_id: int, force_remote: bool = False):
        _ = force_remote
        songs = self._payload.get("songs", [])
        for song in songs:
            if not isinstance(song, dict) or not self._song_available(song):
                continue
            try:
                internal_song_id = int(song.get("internal_song_id", 0))
            except Exception:
                continue
            if internal_song_id == int(song_id):
                return dict(song)
        return None

    def get_events_info(self) -> dict[str, dict[str, Any]]:
        events = self._payload.get("events", [])
        result: dict[str, dict[str, Any]] = {}
        for event in events:
            if not isinstance(event, dict) or not self._event_available(event):
                continue
            try:
                event_id = int(event.get("event_id", 0))
            except Exception:
                continue
            if event_id <= 0:
                continue
            result[str(event_id)] = dict(event)
        return result

    def get_bands_info(self) -> dict[str, dict[str, Any]]:
        bands = self._payload.get("bands", [])
        result: dict[str, dict[str, Any]] = {}
        for band in bands:
            if not isinstance(band, dict) or not self._band_available(band):
                continue
            try:
                band_id = int(band.get("internal_band_id", 0))
            except Exception:
                continue
            if band_id <= 0:
                continue
            result[str(band_id)] = dict(band)
        return result

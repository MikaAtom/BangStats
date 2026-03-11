import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from bangstats_server.core.services.band import BandService
from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.song import SongService


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "server" / "bangstats_server" / "core" / "adapters" / "seed_data.json"


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _song_payload(song: Any) -> dict[str, Any]:
    return {
        "internal_song_id": int(song.internal_song_id),
        "tag": song.tag,
        "name": _serialize(song.name),
        "band_id": int(song.band_id),
        "lyricist": _serialize(song.lyricist),
        "composer": _serialize(song.composer),
        "arranger": _serialize(song.arranger),
        "levels": _serialize(song.levels),
        "note_counts": _serialize(song.note_counts),
        "bpm": float(song.bpm),
        "length": float(song.length),
        "published_at": _serialize(song.published_at),
        "closed_at": _serialize(song.closed_at),
        "special": _serialize(song.special),
    }


def _event_payload(event: Any) -> dict[str, Any]:
    return {
        "event_id": int(event.event_id),
        "event_type": event.event_type,
        "event_name": _serialize(event.event_name),
        "event_start_at": _serialize(event.event_start_at),
        "event_end_at": _serialize(event.event_end_at),
        "misc": _serialize(event.misc),
    }


def _band_payload(band: Any) -> dict[str, Any]:
    return {
        "internal_band_id": int(band.internal_band_id),
        "name": _serialize(band.name),
    }


def _inject_edge_cases(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    songs: list[dict[str, Any]] = data.get("songs", [])
    events: list[dict[str, Any]] = data.get("events", [])
    bands: list[dict[str, Any]] = data.get("bands", [])

    max_song_id = max([int(item.get("internal_song_id", 0)) for item in songs] + [0])
    max_event_id = max([int(item.get("event_id", 0)) for item in events] + [0])
    max_band_id = max([int(item.get("internal_band_id", 0)) for item in bands] + [0])

    edge_band_id = max_band_id + 1
    bands.append({"internal_band_id": edge_band_id, "name": {"jp": "テストバンド"}})

    base_note_counts = {"easy": [120], "normal": [260], "hard": [450], "expert": [700], "special": [850]}
    base_levels = {"easy": [8], "normal": [14], "hard": [20], "expert": [26], "special": [29]}

    songs.extend(
        [
            {
                "internal_song_id": max_song_id + 1,
                "tag": "edge_special_chars",
                "name": {"en": "Re:birth day / B.O.F", "jp": "1/3の純情な感情"},
                "band_id": edge_band_id,
                "lyricist": {"en": "Edge"},
                "composer": {"en": "Edge"},
                "arranger": {"en": "Edge"},
                "levels": deepcopy(base_levels),
                "note_counts": deepcopy(base_note_counts),
                "bpm": 185.0,
                "length": 120.0,
                "published_at": {"en": "1710000000000", "jp": "1710000000000", "tw": None, "cn": None, "kr": None},
                "closed_at": None,
                "special": {"note": "edge-case"},
            },
            {
                "internal_song_id": max_song_id + 2,
                "tag": "edge_missing_translation",
                "name": {"jp": "翻訳なし"},
                "band_id": edge_band_id,
                "lyricist": {"jp": "不明"},
                "composer": {"jp": "不明"},
                "arranger": {"jp": "不明"},
                "levels": deepcopy(base_levels),
                "note_counts": deepcopy(base_note_counts),
                "bpm": 172.0,
                "length": 118.0,
                "published_at": {"en": None, "jp": "1710000001000", "tw": None, "cn": None, "kr": None},
                "closed_at": {"jp": "1719999999000"},
                "special": None,
            },
            {
                "internal_song_id": max_song_id + 3,
                "tag": "edge_duplicate_notes_a",
                "name": {"en": "Duplicate Notes A"},
                "band_id": edge_band_id,
                "lyricist": {"en": "Edge"},
                "composer": {"en": "Edge"},
                "arranger": {"en": "Edge"},
                "levels": deepcopy(base_levels),
                "note_counts": deepcopy(base_note_counts),
                "bpm": 160.0,
                "length": 110.0,
                "published_at": {"en": "1710000002000", "jp": "1710000002000", "tw": None, "cn": None, "kr": None},
                "closed_at": None,
                "special": None,
            },
            {
                "internal_song_id": max_song_id + 4,
                "tag": "edge_duplicate_notes_b",
                "name": {"en": "Duplicate Notes B"},
                "band_id": edge_band_id,
                "lyricist": {"en": "Edge"},
                "composer": {"en": "Edge"},
                "arranger": {"en": "Edge"},
                "levels": deepcopy(base_levels),
                "note_counts": deepcopy(base_note_counts),
                "bpm": 161.0,
                "length": 111.0,
                "published_at": {"en": "1710000003000", "jp": "1710000003000", "tw": None, "cn": None, "kr": None},
                "closed_at": None,
                "special": None,
            },
        ]
    )

    events.append(
        {
            "event_id": max_event_id + 1,
            "event_type": "story",
            "event_name": {"en": "Edge Event", "jp": "エッジイベント"},
            "event_start_at": {"en": None, "jp": "1705000000000", "tw": None, "cn": None, "kr": None},
            "event_end_at": {"en": None, "jp": "1706000000000", "tw": None, "cn": None, "kr": None},
            "misc": {"edge_case": True},
        }
    )

    data["songs"] = songs
    data["events"] = events
    data["bands"] = bands
    return data


def main() -> None:
    song_service = SongService()
    event_service = EventService()
    band_service = BandService()

    payload = {
        "songs": [_song_payload(item) for item in song_service.get_all_songs()],
        "events": [_event_payload(item) for item in event_service.get_all_events()],
        "bands": [_band_payload(item) for item in band_service.get_all_bands()],
    }
    payload = _inject_edge_cases(payload)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Seed data exported to {OUT_PATH} "
        f"(songs={len(payload['songs'])}, events={len(payload['events'])}, bands={len(payload['bands'])})"
    )


if __name__ == "__main__":
    main()

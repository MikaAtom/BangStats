from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "clients" / "cli"
if str(CLIENT_PATH) not in sys.path:
    sys.path.insert(0, str(CLIENT_PATH))

from bangstats_cli.api_client import BangStatsAPI


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttpxClient:
    def __init__(self, batch_payloads: list[dict[str, Any]]):
        self._batch_payloads = batch_payloads
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, *, data=None, files=None, json=None, timeout=None):
        self.calls.append(
            {
                "method": "post",
                "url": url,
                "data": data,
                "files_count": len(files) if files else 0,
                "json": json,
                "timeout": timeout,
            }
        )
        if url == "/api/scans":
            call_index = len([c for c in self.calls if c["url"] == "/api/scans"]) - 1
            payload = self._batch_payloads[call_index]
            return _FakeResponse(payload)
        if url == "/api/scans/filename-diff":
            return _FakeResponse(
                {
                    "requested_total": len(json["filenames"]),
                    "already_scanned_count": 1,
                    "to_scan_count": max(0, len(json["filenames"]) - 1),
                    "already_scanned_filenames": json["filenames"][:1],
                    "to_scan_filenames": json["filenames"][1:],
                }
            )
        if url == "/api/scans/check-local-path":
            return _FakeResponse(
                {"is_local": True, "canonical_path": json["folder_path"]}
            )
        if url == "/api/scans/scan-local-folder":
            return _FakeResponse(
                {
                    "total_scanned": len(json["filenames"]),
                    "successful": len(json["filenames"]),
                    "errors": {},
                    "error_files": {},
                    "validated": len(json["filenames"]),
                    "persisted": len(json["filenames"]),
                    "failed_to_persist": 0,
                    "skipped_duplicates": 0,
                    "error_rate": 0.0,
                    "additional": {},
                }
            )
        raise AssertionError(f"Unexpected URL in fake client: {url}")

    def get(self, url: str, *, params=None):
        self.calls.append({"method": "get", "url": url, "params": params})
        if "/stats/songs/search" in url:
            return _FakeResponse(
                {
                    "query": params["q"],
                    "limit": int(params["limit"]),
                    "results": [
                        {
                            "song_id": 125,
                            "song_name": "Unite! From A To Z",
                        }
                    ],
                }
            )
        if "/stats/songs/" in url:
            return _FakeResponse(
                {
                    "song_id": 125,
                    "song_name": "Unite! From A To Z",
                    "requested_difficulty": params.get("difficulty"),
                    "difficulty_overview": [
                        {
                            "difficulty": "hard",
                            "total_plays": 2,
                            "first_played": {
                                "timestamp": "2026-03-01T12:00:00",
                                "filename": "a.png",
                            },
                        }
                    ],
                    "detail": {
                        "total_plays": 2,
                        "total_fc": 1,
                        "total_ap": 0,
                        "accuracy": 95.0,
                        "first_played": {
                            "timestamp": "2026-03-01T12:00:00",
                            "filename": "a.png",
                        },
                        "last_played": {
                            "timestamp": "2026-03-02T12:00:00",
                            "filename": "b.png",
                        },
                        "first_fc": {
                            "timestamp": "2026-03-02T12:00:00",
                            "filename": "b.png",
                        },
                        "last_fc": {
                            "timestamp": "2026-03-02T12:00:00",
                            "filename": "b.png",
                        },
                        "first_ap": None,
                        "last_ap": None,
                        "plays_before_fc": 1,
                        "plays_before_ap": None,
                    }
                    if params.get("difficulty")
                    else None,
                }
            )
        raise AssertionError(f"Unexpected URL in fake client.get: {url}")

    def close(self) -> None:
        return None


def test_scan_images_batches_upload_and_aggregates(tmp_path: Path):
    files: list[Path] = []
    for idx in range(205):
        target = tmp_path / f"Screenshot_{idx}.png"
        target.write_bytes(b"x")
        files.append(target)

    batch_a = {
        "total_scanned": 200,
        "successful": 190,
        "validated": 190,
        "persisted": 180,
        "failed_to_persist": 5,
        "skipped_duplicates": 5,
        "errors": {"not_found_errors": 10},
        "error_files": {"not_found_errors": ["a.json"]},
        "additional": {"provider": "gemini", "parallel_enabled": False},
    }
    batch_b = {
        "total_scanned": 5,
        "successful": 5,
        "validated": 5,
        "persisted": 4,
        "failed_to_persist": 0,
        "skipped_duplicates": 1,
        "errors": {"not_found_errors": 0},
        "error_files": {"not_found_errors": ["b.json"]},
        "additional": {"provider": "gemini", "parallel_enabled": False},
    }

    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([batch_a, batch_b])
    api._client = fake_client
    api.SCAN_UPLOAD_BATCH_SIZE = 200

    result = api.scan_images(user_id=3, image_paths=files)

    assert len(fake_client.calls) == 2
    assert fake_client.calls[0]["files_count"] == 200
    assert fake_client.calls[1]["files_count"] == 5
    assert all(call["timeout"] is None for call in fake_client.calls)

    assert result["total_scanned"] == 205
    assert result["successful"] == 195
    assert result["persisted"] == 184
    assert result["failed_to_persist"] == 5
    assert result["skipped_duplicates"] == 6
    assert result["errors"]["not_found_errors"] == 10
    assert result["error_files"]["not_found_errors"] == ["a.json", "b.json"]
    assert result["additional"]["upload_mode"] == "chunked"
    assert result["additional"]["upload_batches"] == 2
    assert result["additional"]["upload_batch_size"] == 200


def test_precheck_and_local_scan_client_methods():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    diff = api.get_scan_filename_diff(user_id=7, filenames=["a.png", "b.png"])
    assert diff["requested_total"] == 2
    assert diff["already_scanned_filenames"] == ["a.png"]
    assert diff["to_scan_filenames"] == ["b.png"]

    local = api.check_scan_local_path("/srv/data/BangStats/user/screens")
    assert local["is_local"] is True
    assert local["canonical_path"] == "/srv/data/BangStats/user/screens"

    result = api.scan_local_folder(
        user_id=7,
        folder_path="/srv/data/BangStats/user/screens",
        filenames=["b.png"],
        parallel_workers=2,
        keys_per_worker=1,
    )
    assert result["total_scanned"] == 1
    assert result["persisted"] == 1


def test_song_stats_client_methods():
    api = BangStatsAPI("http://localhost:8000")
    fake_client = _FakeHttpxClient([])
    api._client = fake_client

    search = api.search_user_stat_songs(
        user_id=7,
        query="unite",
        server="en",
        limit=10,
    )
    assert search["query"] == "unite"
    assert search["results"][0]["song_id"] == 125

    overview = api.get_user_song_stats(user_id=7, song_id=125, server="en")
    assert overview["song_id"] == 125
    assert overview["detail"] is None

    detail = api.get_user_song_stats(
        user_id=7,
        song_id=125,
        server="en",
        difficulty="hard",
    )
    assert detail["requested_difficulty"] == "hard"
    assert detail["detail"]["total_plays"] == 2

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class BangStatsAPI:
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        response = self._client.get("/api/users", params={"username": username})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_user(self, user_id: int) -> dict[str, Any]:
        response = self._client.get(f"/api/users/{user_id}")
        response.raise_for_status()
        return response.json()

    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post("/api/users", json=payload)
        response.raise_for_status()
        return response.json()

    def update_user(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.patch(f"/api/users/{user_id}", json=payload)
        response.raise_for_status()
        return response.json()

    def sync(self, server: str) -> dict[str, Any]:
        response = self._client.post("/api/sync", json={"server": server})
        response.raise_for_status()
        return response.json()

    def get_db_counts(self) -> dict[str, int]:
        response = self._client.get("/api/db/counts")
        response.raise_for_status()
        return response.json()

    def get_current_event(self, server: str) -> dict[str, Any] | None:
        response = self._client.get("/api/events/current", params={"server": server})
        response.raise_for_status()
        return response.json()

    def scan_images(self, user_id: int, image_paths: list[Path]) -> dict[str, Any]:
        files = []
        file_handles = []
        try:
            for path in image_paths:
                handle = path.open("rb")
                file_handles.append(handle)
                files.append(("files", (path.name, handle, "application/octet-stream")))
            response = self._client.post(
                "/api/scans",
                data={"user_id": str(user_id)},
                files=files,
            )
            response.raise_for_status()
            return response.json()
        finally:
            for handle in file_handles:
                handle.close()

    def get_user_stats(self, user_id: int) -> dict[str, Any]:
        response = self._client.get(f"/api/users/{user_id}/stats")
        response.raise_for_status()
        return response.json()

    def flush(
        self,
        *,
        remote_cache: bool = False,
        scan_cache: bool = False,
        db: bool = False,
    ) -> dict[str, Any]:
        response = self._client.post(
            "/api/admin/flush",
            json={
                "remote_cache": remote_cache,
                "scan_cache": scan_cache,
                "db": db,
            },
        )
        response.raise_for_status()
        return response.json()

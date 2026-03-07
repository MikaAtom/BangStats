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

    def create_sync_job(self, server: str, requested_by_user_id: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"server": server}
        if requested_by_user_id is not None:
            payload["requested_by_user_id"] = requested_by_user_id
        response = self._client.post("/api/sync/jobs", json=payload)
        response.raise_for_status()
        return response.json()

    def sync(self, server: str, requested_by_user_id: int | None = None) -> dict[str, Any]:
        # Backward-compatible alias.
        return self.create_sync_job(server, requested_by_user_id=requested_by_user_id)

    def get_sync_job(self, job_id: int) -> dict[str, Any]:
        response = self._client.get(f"/api/sync/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def list_sync_jobs(self, limit: int = 20, status: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        response = self._client.get("/api/sync/jobs", params=params)
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

    def scan_images(
        self,
        user_id: int,
        image_paths: list[Path],
        *,
        parallel_workers: int | None = None,
        keys_per_worker: int | None = None,
    ) -> dict[str, Any]:
        files = []
        file_handles = []
        try:
            for path in image_paths:
                handle = path.open("rb")
                file_handles.append(handle)
                files.append(("files", (path.name, handle, "application/octet-stream")))
            payload = {"user_id": str(user_id)}
            if parallel_workers is not None and keys_per_worker is not None:
                payload["parallel_workers"] = str(parallel_workers)
                payload["keys_per_worker"] = str(keys_per_worker)
            response = self._client.post(
                "/api/scans",
                data=payload,
                files=files,
            )
            response.raise_for_status()
            return response.json()
        finally:
            for handle in file_handles:
                handle.close()

    def import_json_folder(
        self,
        *,
        user_id: int,
        folder_path: str,
        persist_to_db: bool = True,
    ) -> dict[str, Any]:
        response = self._client.post(
            "/api/scans/import-json-folder",
            json={
                "user_id": user_id,
                "folder_path": folder_path,
                "persist_to_db": persist_to_db,
            },
            timeout=None,
        )
        response.raise_for_status()
        return response.json()

    def get_scan_capabilities(self) -> dict[str, Any]:
        response = self._client.get("/api/scans/capabilities")
        response.raise_for_status()
        return response.json()

    def list_scan_errors(self) -> dict[str, Any]:
        response = self._client.get("/api/scans/errors")
        response.raise_for_status()
        return response.json()

    def get_scan_error_detail(self, error_type: str, json_filename: str) -> dict[str, Any]:
        response = self._client.get(f"/api/scans/errors/{error_type}/{json_filename}")
        response.raise_for_status()
        return response.json()

    def correct_scan_error(
        self,
        *,
        user_id: int,
        error_type: str,
        json_filename: str,
        corrected_scan_data: dict[str, Any],
        persist_to_db: bool = True,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/api/scans/errors/{error_type}/{json_filename}/correct",
            json={
                "user_id": user_id,
                "corrected_scan_data": corrected_scan_data,
                "persist_to_db": persist_to_db,
            },
        )
        response.raise_for_status()
        return response.json()

    def revalidate_error_category(
        self,
        *,
        user_id: int,
        error_type: str,
        persist_to_db: bool = True,
        progress_every: int = 500,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/api/scans/errors/{error_type}/revalidate",
            json={
                "user_id": user_id,
                "persist_to_db": persist_to_db,
                "progress_every": progress_every,
            },
            timeout=None,
        )
        response.raise_for_status()
        return response.json()

    def rescan_error_category(
        self,
        *,
        user_id: int,
        error_type: str,
        persist_to_db: bool = True,
        progress_every: int = 500,
        model: str | None = None,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/api/scans/errors/{error_type}/rescan",
            json={
                "user_id": user_id,
                "persist_to_db": persist_to_db,
                "progress_every": progress_every,
                "model": model,
            },
            timeout=None,
        )
        response.raise_for_status()
        return response.json()

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

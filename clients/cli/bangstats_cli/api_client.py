from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class BangStatsAPI:
    SCAN_UPLOAD_BATCH_SIZE = 200

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
        if not image_paths:
            return self._init_scan_aggregate()

        aggregate = self._init_scan_aggregate()
        batch_size = self.SCAN_UPLOAD_BATCH_SIZE
        total_batches = (len(image_paths) + batch_size - 1) // batch_size

        for start in range(0, len(image_paths), batch_size):
            batch = image_paths[start : start + batch_size]
            files = []
            file_handles = []
            try:
                for path in batch:
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
                    timeout=None,
                )
                response.raise_for_status()
                batch_result = response.json()
                self._merge_scan_aggregate(aggregate, batch_result)
            finally:
                for handle in file_handles:
                    handle.close()

        aggregate["error_rate"] = self._calculate_error_rate(
            total_scanned=aggregate["total_scanned"],
            successful=aggregate["successful"],
        )
        additional = aggregate.setdefault("additional", {})
        additional["upload_mode"] = "chunked" if total_batches > 1 else "single"
        additional["upload_batches"] = total_batches
        additional["upload_batch_size"] = batch_size
        return aggregate

    def get_scan_filename_diff(self, *, user_id: int, filenames: list[str]) -> dict[str, Any]:
        response = self._client.post(
            "/api/scans/filename-diff",
            json={"user_id": user_id, "filenames": filenames},
            timeout=None,
        )
        response.raise_for_status()
        return response.json()

    def check_scan_local_path(self, folder_path: str) -> dict[str, Any]:
        response = self._client.post(
            "/api/scans/check-local-path",
            json={"folder_path": folder_path},
        )
        response.raise_for_status()
        return response.json()

    def scan_local_folder(
        self,
        *,
        user_id: int,
        folder_path: str,
        filenames: list[str],
        parallel_workers: int | None = None,
        keys_per_worker: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_id": user_id,
            "folder_path": folder_path,
            "filenames": filenames,
        }
        if parallel_workers is not None and keys_per_worker is not None:
            payload["parallel_workers"] = parallel_workers
            payload["keys_per_worker"] = keys_per_worker
        response = self._client.post(
            "/api/scans/scan-local-folder",
            json=payload,
            timeout=None,
        )
        response.raise_for_status()
        return response.json()

    def _init_scan_aggregate(self) -> dict[str, Any]:
        return {
            "total_scanned": 0,
            "successful": 0,
            "errors": {},
            "error_files": {},
            "validated": 0,
            "persisted": 0,
            "failed_to_persist": 0,
            "skipped_duplicates": 0,
            "error_rate": 0.0,
            "additional": {},
        }

    def _merge_scan_aggregate(self, aggregate: dict[str, Any], batch_result: dict[str, Any]) -> None:
        for key in [
            "total_scanned",
            "successful",
            "validated",
            "persisted",
            "failed_to_persist",
            "skipped_duplicates",
        ]:
            aggregate[key] = int(aggregate.get(key, 0)) + int(batch_result.get(key, 0))

        for error_type, count in (batch_result.get("errors") or {}).items():
            aggregate["errors"][error_type] = int(aggregate["errors"].get(error_type, 0)) + int(
                count
            )

        for error_type, file_list in (batch_result.get("error_files") or {}).items():
            existing = aggregate["error_files"].setdefault(error_type, [])
            if isinstance(file_list, list):
                existing.extend(file_list)

        batch_additional = batch_result.get("additional")
        if isinstance(batch_additional, dict):
            for key, value in batch_additional.items():
                aggregate["additional"].setdefault(key, value)

    def _calculate_error_rate(self, *, total_scanned: int, successful: int) -> float:
        if total_scanned <= 0:
            return 0.0
        failed = max(0, total_scanned - successful)
        return (failed / total_scanned) * 100.0

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

    def search_user_stat_songs(
        self,
        user_id: int,
        query: str,
        *,
        server: str = "en",
        limit: int = 20,
    ) -> dict[str, Any]:
        response = self._client.get(
            f"/api/users/{user_id}/stats/songs/search",
            params={"q": query, "server": server, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def get_user_song_stats(
        self,
        user_id: int,
        song_id: int,
        *,
        server: str = "en",
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"server": server}
        if difficulty:
            params["difficulty"] = difficulty
        response = self._client.get(
            f"/api/users/{user_id}/stats/songs/{song_id}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_user_stats_milestones(self, user_id: int) -> dict[str, Any]:
        response = self._client.get(f"/api/users/{user_id}/stats/milestones")
        response.raise_for_status()
        return response.json()

    def get_user_stats_activity(
        self,
        user_id: int,
        *,
        preset: str | None = "30d",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if from_date or to_date:
            if from_date:
                params["from_date"] = from_date
            if to_date:
                params["to_date"] = to_date
        elif preset:
            params["preset"] = preset

        response = self._client.get(
            f"/api/users/{user_id}/stats/activity",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_user_stats_calendar(
        self,
        user_id: int,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if year is not None:
            params["year"] = year
        if month is not None:
            params["month"] = month
        response = self._client.get(
            f"/api/users/{user_id}/stats/calendar",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_user_stats_insights(
        self,
        user_id: int,
        *,
        preset: str | None = "30d",
        from_date: str | None = None,
        to_date: str | None = None,
        session_gap_minutes: int = 45,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"session_gap_minutes": session_gap_minutes}
        if from_date or to_date:
            if from_date:
                params["from_date"] = from_date
            if to_date:
                params["to_date"] = to_date
        elif preset:
            params["preset"] = preset
        response = self._client.get(
            f"/api/users/{user_id}/stats/insights",
            params=params,
        )
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

from threading import Lock
from typing import Optional

from bangstats_server.core.db.models.sync_job import SyncJob
from bangstats_server.core.db.repositories.sync_job_repository import SyncJobRepository

ALLOWED_SYNC_STATUSES = {"queued", "running", "succeeded", "failed"}


class SyncJobService:
    _create_lock = Lock()

    def create_job(
        self,
        *,
        server: str,
        requested_by_user_id: Optional[int] = None,
    ) -> SyncJob:
        with self._create_lock:
            with SyncJobRepository() as repo:
                active = repo.get_active_job()
                if active:
                    raise ValueError(
                        f"Sync already active (job_id={active.id}, status={active.status})"
                    )
                return repo.create_job(
                    server=server,
                    requested_by_user_id=requested_by_user_id,
                )

    def get_job(self, job_id: int) -> Optional[SyncJob]:
        with SyncJobRepository() as repo:
            return repo.get_by_id(job_id)

    def list_jobs(self, *, limit: int = 20, status: Optional[str] = None) -> list[SyncJob]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        if status and status not in ALLOWED_SYNC_STATUSES:
            raise ValueError(
                f"invalid status '{status}', expected one of: {', '.join(sorted(ALLOWED_SYNC_STATUSES))}"
            )
        with SyncJobRepository() as repo:
            return repo.list_jobs(limit=limit, status=status)

    def mark_running(self, job_id: int) -> Optional[SyncJob]:
        with SyncJobRepository() as repo:
            return repo.mark_running(job_id)

    def mark_succeeded(self, job_id: int, *, songs: int, events: int, bands: int) -> Optional[SyncJob]:
        with SyncJobRepository() as repo:
            return repo.mark_succeeded(job_id, songs=songs, events=events, bands=bands)

    def mark_failed(self, job_id: int, *, error_message: str) -> Optional[SyncJob]:
        with SyncJobRepository() as repo:
            return repo.mark_failed(job_id, error_message=error_message)

    def fail_all_active_jobs(self, *, error_message: str) -> int:
        with SyncJobRepository() as repo:
            return repo.mark_all_active_failed(error_message=error_message)

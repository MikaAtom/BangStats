from threading import Lock
from typing import Optional

from bangstats_server.core.db.models.scan_job import ScanJob
from bangstats_server.core.db.repositories.scan_job_repository import ScanJobRepository

ALLOWED_SCAN_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}


class ScanJobService:
    _create_lock = Lock()

    def create_job(
        self,
        *,
        user_id: int,
        source_type: str,
        folder_path: Optional[str],
        total_files: int,
        parallel_workers: Optional[int] = None,
        keys_per_worker: Optional[int] = None,
    ) -> ScanJob:
        with self._create_lock:
            with ScanJobRepository() as repo:
                return repo.create_job(
                    user_id=user_id,
                    source_type=source_type,
                    folder_path=folder_path,
                    total_files=total_files,
                    parallel_workers=parallel_workers,
                    keys_per_worker=keys_per_worker,
                )

    def get_job(self, job_id: int) -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.get_by_id(job_id)

    def list_jobs_for_user(
        self,
        *,
        user_id: int,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> list[ScanJob]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        if status and status not in ALLOWED_SCAN_STATUSES:
            raise ValueError(
                f"invalid status '{status}', expected one of: {', '.join(sorted(ALLOWED_SCAN_STATUSES))}"
            )
        with ScanJobRepository() as repo:
            return repo.list_jobs_for_user(user_id=user_id, limit=limit, status=status)

    def list_active_jobs(self, *, user_id: Optional[int] = None) -> list[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.list_active_jobs(user_id=user_id)

    def mark_running(self, job_id: int) -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.mark_running(job_id)

    def update_progress(
        self,
        job_id: int,
        *,
        processed: int,
        successful: int,
        validated: int,
        persisted: int,
        failed_to_persist: int,
        skipped_duplicates: int,
        errors: dict[str, int],
        error_files: dict[str, list[str]],
    ) -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.update_progress(
                job_id,
                processed=processed,
                successful=successful,
                validated=validated,
                persisted=persisted,
                failed_to_persist=failed_to_persist,
                skipped_duplicates=skipped_duplicates,
                errors=errors,
                error_files=error_files,
            )

    def request_cancel(self, job_id: int) -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.request_cancel(job_id)

    def mark_cancelled(self, job_id: int, *, error_message: str = "Cancelled by user") -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.mark_cancelled(job_id, error_message=error_message)

    def mark_succeeded(self, job_id: int) -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.mark_succeeded(job_id)

    def mark_failed(self, job_id: int, *, error_message: str) -> Optional[ScanJob]:
        with ScanJobRepository() as repo:
            return repo.mark_failed(job_id, error_message=error_message)

    def fail_all_active_jobs(self, *, error_message: str) -> int:
        with ScanJobRepository() as repo:
            return repo.mark_all_active_failed(error_message=error_message)

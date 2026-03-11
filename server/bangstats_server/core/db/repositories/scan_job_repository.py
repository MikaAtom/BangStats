from datetime import datetime
from typing import Optional

from sqlmodel import desc, select

from bangstats_server.core.db import get_session
from bangstats_server.core.db.models.scan_job import ScanJob

ACTIVE_SCAN_STATUSES = {"queued", "running"}


class ScanJobRepository:
    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, job_id: int) -> Optional[ScanJob]:
        return self._session.get(ScanJob, job_id)

    def list_jobs_for_user(
        self,
        *,
        user_id: int,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> list[ScanJob]:
        statement = select(ScanJob).where(ScanJob.user_id == user_id)
        if status:
            statement = statement.where(ScanJob.status == status)
        statement = statement.order_by(desc(ScanJob.created_at)).limit(limit)
        return self._session.exec(statement).all()

    def list_active_jobs(self, *, user_id: Optional[int] = None) -> list[ScanJob]:
        statement = select(ScanJob).where(ScanJob.status.in_(ACTIVE_SCAN_STATUSES))
        if user_id is not None:
            statement = statement.where(ScanJob.user_id == user_id)
        statement = statement.order_by(desc(ScanJob.created_at))
        return self._session.exec(statement).all()

    def create_job(
        self,
        *,
        user_id: int,
        source_type: str,
        folder_path: Optional[str],
        total_files: int,
        parallel_workers: Optional[int],
        keys_per_worker: Optional[int],
    ) -> ScanJob:
        job = ScanJob(
            user_id=user_id,
            source_type=source_type,
            folder_path=folder_path,
            total_files=total_files,
            parallel_workers=parallel_workers,
            keys_per_worker=keys_per_worker,
        )
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_running(self, job_id: int) -> Optional[ScanJob]:
        job = self._session.get(ScanJob, job_id)
        if not job:
            return None
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.error_message = None
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

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
        job = self._session.get(ScanJob, job_id)
        if not job:
            return None
        job.processed = max(0, processed)
        job.successful = max(0, successful)
        job.validated = max(0, validated)
        job.persisted = max(0, persisted)
        job.failed_to_persist = max(0, failed_to_persist)
        job.skipped_duplicates = max(0, skipped_duplicates)
        job.errors = errors or {}
        job.error_files = error_files or {}
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def request_cancel(self, job_id: int) -> Optional[ScanJob]:
        job = self._session.get(ScanJob, job_id)
        if not job:
            return None
        job.cancelled = True
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_cancelled(self, job_id: int, *, error_message: str = "Cancelled by user") -> Optional[ScanJob]:
        job = self._session.get(ScanJob, job_id)
        if not job:
            return None
        job.status = "cancelled"
        job.finished_at = datetime.utcnow()
        job.error_message = error_message
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_succeeded(self, job_id: int) -> Optional[ScanJob]:
        job = self._session.get(ScanJob, job_id)
        if not job:
            return None
        job.status = "succeeded"
        job.finished_at = datetime.utcnow()
        job.error_message = None
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_failed(self, job_id: int, *, error_message: str) -> Optional[ScanJob]:
        job = self._session.get(ScanJob, job_id)
        if not job:
            return None
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.error_message = error_message
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_all_active_failed(self, *, error_message: str) -> int:
        statement = select(ScanJob).where(ScanJob.status.in_(ACTIVE_SCAN_STATUSES))
        jobs = self._session.exec(statement).all()
        if not jobs:
            return 0
        now = datetime.utcnow()
        for job in jobs:
            job.status = "failed"
            job.finished_at = now
            job.error_message = error_message
            self._session.add(job)
        self._session.commit()
        return len(jobs)

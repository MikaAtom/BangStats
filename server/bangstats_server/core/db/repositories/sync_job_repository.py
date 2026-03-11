from datetime import datetime
from typing import Optional

from sqlmodel import desc, select

from bangstats_server.core.db import get_session
from bangstats_server.core.db.models.sync_job import SyncJob


ACTIVE_SYNC_STATUSES = {"queued", "running"}


class SyncJobRepository:
    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, job_id: int) -> Optional[SyncJob]:
        return self._session.get(SyncJob, job_id)

    def get_active_job(self) -> Optional[SyncJob]:
        stmt = (
            select(SyncJob)
            .where(SyncJob.status.in_(ACTIVE_SYNC_STATUSES))
            .order_by(desc(SyncJob.created_at))
        )
        return self._session.exec(stmt).first()

    def list_jobs(
        self,
        *,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> list[SyncJob]:
        stmt = select(SyncJob)
        if status:
            stmt = stmt.where(SyncJob.status == status)
        stmt = stmt.order_by(desc(SyncJob.created_at)).limit(limit)
        return self._session.exec(stmt).all()

    def create_job(
        self,
        *,
        server: str,
        requested_by_user_id: Optional[int] = None,
    ) -> SyncJob:
        job = SyncJob(server=server, requested_by_user_id=requested_by_user_id)
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_running(self, job_id: int) -> Optional[SyncJob]:
        job = self._session.get(SyncJob, job_id)
        if not job:
            return None
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.error_message = None
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_succeeded(self, job_id: int, *, songs: int, events: int, bands: int) -> Optional[SyncJob]:
        job = self._session.get(SyncJob, job_id)
        if not job:
            return None
        job.status = "succeeded"
        job.finished_at = datetime.utcnow()
        job.songs = songs
        job.events = events
        job.bands = bands
        job.error_message = None
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def mark_failed(self, job_id: int, *, error_message: str) -> Optional[SyncJob]:
        job = self._session.get(SyncJob, job_id)
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
        stmt = select(SyncJob).where(SyncJob.status.in_(ACTIVE_SYNC_STATUSES))
        jobs = self._session.exec(stmt).all()
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

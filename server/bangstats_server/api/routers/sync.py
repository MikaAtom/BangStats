from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger

from bangstats_server.api.schemas.sync import (
    CountsResponse,
    SyncJobListResponse,
    SyncJobResponse,
    SyncRequest,
)
from bangstats_server.core.db.models.sync_job import SyncJob
from bangstats_server.core.services.sync_job import SyncJobService
from bangstats_server.core.sync import get_db_counts, update_db

router = APIRouter()


def _to_sync_job_response(job: SyncJob) -> SyncJobResponse:
    return SyncJobResponse(
        id=int(job.id or 0),
        server=job.server,
        status=job.status,
        requested_by_user_id=job.requested_by_user_id,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        songs=job.songs,
        events=job.events,
        bands=job.bands,
        error_message=job.error_message,
    )


def _run_sync_job(job_id: int, server: str) -> None:
    service = SyncJobService()
    service.mark_running(job_id)
    try:
        songs, events, bands = update_db(server)
        service.mark_succeeded(job_id, songs=songs, events=events, bands=bands)
    except Exception as exc:
        logger.exception("Sync job {} failed", job_id)
        service.mark_failed(job_id, error_message=str(exc))


@router.post("/sync/jobs", response_model=SyncJobResponse)
def create_sync_job(data: SyncRequest, background_tasks: BackgroundTasks):
    service = SyncJobService()
    try:
        job = service.create_job(
            server=data.server,
            requested_by_user_id=data.requested_by_user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already active" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    background_tasks.add_task(_run_sync_job, int(job.id), job.server)
    return _to_sync_job_response(job)


@router.get("/sync/jobs/{job_id}", response_model=SyncJobResponse)
def get_sync_job(job_id: int):
    service = SyncJobService()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return _to_sync_job_response(job)


@router.get("/sync/jobs", response_model=SyncJobListResponse)
def list_sync_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None),
):
    service = SyncJobService()
    try:
        jobs = service.list_jobs(limit=limit, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SyncJobListResponse(jobs=[_to_sync_job_response(job) for job in jobs])


@router.post("/sync", response_model=SyncJobResponse)
def sync_data(data: SyncRequest, background_tasks: BackgroundTasks):
    """
    Backward-compatible alias for starting async sync jobs.
    """
    return create_sync_job(data, background_tasks)


@router.get("/db/counts", response_model=CountsResponse)
def get_counts():
    songs, events, bands = get_db_counts()
    return CountsResponse(songs=songs, events=events, bands=bands)

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder

from bangstats_server.api.dependencies import assert_user_scope, get_current_user
from bangstats_server.api.schemas.scans import (
    AuthorizeServerFolderRequest,
    AuthorizeServerFolderResponse,
    CheckLocalPathRequest,
    CheckLocalPathResponse,
    ErrorCategoryActionRequest,
    ErrorCategoryActionResponse,
    ErrorCorrectionRequest,
    ErrorCorrectionResponse,
    ErrorDetailResponse,
    ErrorListResponse,
    FilenameDiffRequest,
    FilenameDiffResponse,
    ImportJsonFolderRequest,
    ScanJobCreateRequest,
    ScanJobListResponse,
    ScanJobResponse,
    ScanLocalFolderRequest,
    ScanCapabilitiesResponse,
    ScanResponse,
    UploadResponse,
    UploadUsageResponse,
)
from bangstats_server.core.config import (
    BANGSTATS_ENV,
    DEV_SIMULATE_SCREENSHOT_LOCATIONS,
    SCAN_MASTER_KEY,
    SCAN_SERVER_FOLDER_WHITELIST,
)
from bangstats_server.core.db.models.scan_job import ScanJob
from bangstats_server.core.services.scan import ScanService
from bangstats_server.core.db.models.user import User
from bangstats_server.core.services.dev_simulation import DevSimulationService
from bangstats_server.core.services.scan_job import ScanJobService
from bangstats_server.core.services.upload_storage import UploadStorageService
from bangstats_server.core.services.user import UserService

router = APIRouter()


def get_scan_service() -> ScanService:
    try:
        return ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _to_scan_job_response(job: ScanJob) -> ScanJobResponse:
    payload = jsonable_encoder(job)
    return ScanJobResponse(**payload)


def _is_within_whitelist(path: Path) -> bool:
    if not SCAN_SERVER_FOLDER_WHITELIST:
        return True
    try:
        candidate = path.resolve()
    except Exception:
        return False
    for allowed in SCAN_SERVER_FOLDER_WHITELIST:
        try:
            candidate.relative_to(allowed.resolve())
            return True
        except Exception:
            continue
    return False


def _resolve_server_folder_path(*, user_id: int, folder_path: str) -> str:
    candidate = Path(folder_path).expanduser()
    if BANGSTATS_ENV == "dev" and DEV_SIMULATE_SCREENSHOT_LOCATIONS:
        candidate = DevSimulationService().resolve_server_folder_path(user_id, folder_path)
    return str(candidate)


def _validate_server_folder_path(
    *,
    current_user: User,
    user_id: int,
    folder_path: str,
    scan_service: ScanService,
) -> dict:
    if not current_user.server_folder_authorized:
        raise HTTPException(status_code=403, detail="Server folder access is not authorized")
    candidate = _resolve_server_folder_path(user_id=user_id, folder_path=folder_path)
    if not _is_within_whitelist(Path(candidate)):
        raise HTTPException(status_code=403, detail="Path is not inside server folder whitelist")
    locality = scan_service.check_local_scan_path(candidate)
    if locality.get("is_local"):
        locality["canonical_path"] = str(Path(locality.get("canonical_path") or candidate).expanduser())
    return locality


def _run_scan_job(
    *,
    job_id: int,
    user_id: int,
    folder_path: str,
    image_list: list[str],
    parallel_workers: int | None,
    keys_per_worker: int | None,
) -> None:
    scan_job_service = ScanJobService()
    current = scan_job_service.get_job(job_id)
    if not current:
        return
    if current.cancelled:
        scan_job_service.mark_cancelled(job_id)
        return

    scan_job_service.mark_running(job_id)
    scan_service = ScanService()
    try:
        def on_progress(payload: dict) -> None:
            current_job = scan_job_service.get_job(job_id)
            if current_job and current_job.cancelled:
                raise RuntimeError("__scan_job_cancelled__")
            scan_job_service.update_progress(
                job_id,
                processed=int(payload.get("total_scanned", 0)),
                successful=int(payload.get("successful", 0)),
                validated=int(payload.get("validated", 0)),
                persisted=int(payload.get("persisted", 0)),
                failed_to_persist=int(payload.get("failed_to_persist", 0)),
                skipped_duplicates=int(payload.get("skipped_duplicates", 0)),
                errors=payload.get("errors") or {},
                error_files=payload.get("error_files") or {},
            )

        result = scan_service.scan_images(
            images_folder=folder_path,
            image_list=image_list,
            user_id=user_id,
            persist_to_db=True,
            parallel_workers=parallel_workers,
            keys_per_worker=keys_per_worker,
            on_progress=on_progress,
            progress_every=5,
        )
        on_progress(result)
        post = scan_job_service.get_job(job_id)
        if post and post.cancelled:
            scan_job_service.mark_cancelled(job_id)
            return
        scan_job_service.mark_succeeded(job_id)
    except Exception as exc:
        if str(exc) == "__scan_job_cancelled__":
            scan_job_service.mark_cancelled(job_id)
            return
        scan_job_service.mark_failed(job_id, error_message=str(exc))


@router.post("/scans/filename-diff", response_model=FilenameDiffResponse)
def get_scan_filename_diff(
    data: FilenameDiffRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    return scan_service.compute_filename_diff(
        user_id=user_id,
        filenames=data.filenames,
    )


@router.post("/scans/check-local-path", response_model=CheckLocalPathResponse)
def check_scan_local_path(
    data: CheckLocalPathRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    requested_user_id = data.user_id or int(current_user.id)
    assert_user_scope(requested_user_id, current_user)
    return _validate_server_folder_path(
        current_user=current_user,
        user_id=requested_user_id,
        folder_path=data.folder_path,
        scan_service=scan_service,
    )


@router.post("/scans/authorize-server-folder", response_model=AuthorizeServerFolderResponse)
def authorize_server_folder(
    data: AuthorizeServerFolderRequest,
    current_user: User = Depends(get_current_user),
):
    if not SCAN_MASTER_KEY:
        raise HTTPException(status_code=403, detail="Server folder mode is disabled")
    if data.master_key != SCAN_MASTER_KEY:
        raise HTTPException(status_code=403, detail="Invalid master key")
    user = UserService().update_user(int(current_user.id), {"server_folder_authorized": True})
    return AuthorizeServerFolderResponse(authorized=bool(user.server_folder_authorized))


@router.post("/scans/scan-local-folder", response_model=ScanResponse)
def scan_local_folder(
    data: ScanLocalFolderRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    try:
        return scan_service.scan_local_folder(
            user_id=user_id,
            folder_path=data.folder_path,
            filenames=data.filenames,
            parallel_workers=data.parallel_workers,
            keys_per_worker=data.keys_per_worker,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scans", response_model=ScanResponse)
def create_scan(
    user_id: int = Form(...),
    files: list[UploadFile] = File(...),
    parallel_workers: int | None = Form(default=None),
    keys_per_worker: int | None = Form(default=None),
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    with tempfile.TemporaryDirectory(prefix="bangstats-scan-") as tmp_dir:
        filenames: list[str] = []
        for upload in files:
            if not upload.filename:
                continue
            safe_name = Path(upload.filename).name
            target = os.path.join(tmp_dir, safe_name)
            content = upload.file.read()
            with open(target, "wb") as out:
                out.write(content)
            filenames.append(safe_name)

        if not filenames:
            raise HTTPException(status_code=400, detail="No valid files provided")

        try:
            return scan_service.scan_images(
                images_folder=tmp_dir,
                image_list=sorted(filenames),
                user_id=user_id,
                persist_to_db=True,
                parallel_workers=parallel_workers,
                keys_per_worker=keys_per_worker,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scans/upload", response_model=UploadResponse)
def upload_scan_files(
    user_id: int = Form(...),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    payloads: list[tuple[str, bytes]] = []
    total_bytes = 0
    for upload in files:
        if not upload.filename:
            continue
        content = upload.file.read()
        if content is None:
            continue
        safe_name = Path(upload.filename).name
        payloads.append((safe_name, content))
        total_bytes += len(content)

    if not payloads:
        raise HTTPException(status_code=400, detail="No valid files provided")

    storage = UploadStorageService()
    allowed, message = storage.check_limits(
        user_id=user_id,
        incoming_files_count=len(payloads),
        incoming_total_bytes=total_bytes,
    )
    if not allowed:
        raise HTTPException(status_code=413, detail=message or "Upload storage limit exceeded")

    saved = storage.save_named_payloads(user_id, payloads)
    usage = storage.get_usage(user_id)
    return UploadResponse(
        uploaded_files=len(saved),
        total_uploaded_for_user=int(usage["file_count"]),
        total_storage_mb_for_user=float(usage["total_size_mb"]),
    )


@router.get("/scans/upload-usage", response_model=UploadUsageResponse)
def get_upload_usage(user_id: int, current_user: User = Depends(get_current_user)):
    user_id = assert_user_scope(user_id, current_user)
    usage = UploadStorageService().get_usage(user_id)
    return UploadUsageResponse(
        file_count=int(usage["file_count"]),
        total_size_mb=float(usage["total_size_mb"]),
        oldest_file_age_days=float(usage["oldest_file_age_days"]),
    )


@router.post("/scans/jobs", response_model=ScanJobResponse)
def create_scan_job(
    data: ScanJobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    scan_service: ScanService = Depends(get_scan_service),
):
    user_id = assert_user_scope(data.user_id, current_user)
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".heic", ".heif"}
    scan_job_service = ScanJobService()

    if data.source_type == "upload":
        upload_dir = UploadStorageService().ensure_user_dir(user_id)
        image_list = [
            p.name
            for p in sorted(upload_dir.iterdir())
            if p.is_file() and p.suffix.lower() in allowed_suffixes
        ]
        if data.filenames:
            selected = set(data.filenames)
            image_list = [name for name in image_list if name in selected]
        folder_path = str(upload_dir)
    else:
        if not data.folder_path:
            raise HTTPException(status_code=400, detail="folder_path is required for server_folder source")
        locality = _validate_server_folder_path(
            current_user=current_user,
            user_id=user_id,
            folder_path=data.folder_path,
            scan_service=scan_service,
        )
        if not locality.get("is_local"):
            raise HTTPException(status_code=400, detail="Folder path is not local to server")
        folder_path = locality.get("canonical_path") or data.folder_path
        folder = Path(folder_path)
        if data.filenames:
            image_list = [
                name
                for name in data.filenames
                if (folder / name).is_file() and (folder / name).suffix.lower() in allowed_suffixes
            ]
        else:
            image_list = [
                p.name
                for p in sorted(folder.iterdir())
                if p.is_file() and p.suffix.lower() in allowed_suffixes
            ]

    if not image_list:
        raise HTTPException(status_code=400, detail="No files available for scan job")

    if hasattr(scan_job_service, "list_active_jobs"):
        active_jobs = scan_job_service.list_active_jobs(user_id=user_id)
        for active in active_jobs:
            if active.source_type != data.source_type:
                continue
            if data.source_type == "upload":
                raise HTTPException(status_code=409, detail=f"Scan job #{active.id} is already active for uploads")
            active_path = str(active.folder_path or "").strip()
            requested_path = str(folder_path or "").strip()
            if active_path and requested_path and active_path == requested_path:
                raise HTTPException(status_code=409, detail=f"Scan job #{active.id} is already active for this folder")

    if hasattr(scan_service, "compute_filename_diff"):
        diff = scan_service.compute_filename_diff(user_id=user_id, filenames=image_list)
        image_list = sorted(set(diff.get("to_scan_filenames") or []))
        if not image_list:
            raise HTTPException(status_code=400, detail="No new files to scan")

    job = scan_job_service.create_job(
        user_id=user_id,
        source_type=data.source_type,
        folder_path=folder_path,
        total_files=len(image_list),
        parallel_workers=data.parallel_workers,
        keys_per_worker=data.keys_per_worker,
    )
    background_tasks.add_task(
        _run_scan_job,
        job_id=int(job.id),
        user_id=user_id,
        folder_path=folder_path,
        image_list=image_list,
        parallel_workers=data.parallel_workers,
        keys_per_worker=data.keys_per_worker,
    )
    return _to_scan_job_response(job)


@router.get("/scans/jobs/{job_id}", response_model=ScanJobResponse)
def get_scan_job(job_id: int, current_user: User = Depends(get_current_user)):
    job = ScanJobService().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if int(job.user_id) != int(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden for this user")
    return _to_scan_job_response(job)


@router.get("/scans/jobs", response_model=ScanJobListResponse)
def list_scan_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    try:
        jobs = ScanJobService().list_jobs_for_user(
            user_id=int(current_user.id),
            limit=limit,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScanJobListResponse(jobs=[_to_scan_job_response(job) for job in jobs])


@router.post("/scans/jobs/{job_id}/cancel", response_model=ScanJobResponse)
def cancel_scan_job(job_id: int, current_user: User = Depends(get_current_user)):
    service = ScanJobService()
    current = service.get_job(job_id)
    if not current:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if int(current.user_id) != int(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden for this user")
    if current.status in {"succeeded", "failed", "cancelled"}:
        return _to_scan_job_response(current)

    service.request_cancel(job_id)
    refreshed = service.get_job(job_id)
    if refreshed and refreshed.status == "queued":
        refreshed = service.mark_cancelled(job_id)
    return _to_scan_job_response(refreshed or current)


@router.get("/scans/capabilities", response_model=ScanCapabilitiesResponse)
def get_scan_capabilities(scan_service: ScanService = Depends(get_scan_service)):
    return scan_service.get_scan_capabilities()


@router.post("/scans/import-json-folder", response_model=ScanResponse)
def import_json_folder(
    data: ImportJsonFolderRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    try:
        return scan_service.import_json_folder(
            folder_path=data.folder_path,
            user_id=user_id,
            persist_to_db=data.persist_to_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scans/errors", response_model=ErrorListResponse)
def list_scan_errors(scan_service: ScanService = Depends(get_scan_service)):
    return scan_service.list_error_files()


@router.get("/scans/errors/{error_type}/{json_filename}", response_model=ErrorDetailResponse)
def get_scan_error_detail(
    error_type: str,
    json_filename: str,
    scan_service: ScanService = Depends(get_scan_service),
):
    try:
        return scan_service.get_error_detail(error_type=error_type, json_filename=json_filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/scans/errors/{error_type}/{json_filename}/correct",
    response_model=ErrorCorrectionResponse,
)
def correct_scan_error(
    error_type: str,
    json_filename: str,
    data: ErrorCorrectionRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    try:
        return scan_service.correct_error_file(
            user_id=user_id,
            error_type=error_type,
            json_filename=json_filename,
            corrected_scan_data=data.corrected_scan_data,
            persist_to_db=data.persist_to_db,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/scans/errors/{error_type}/revalidate",
    response_model=ErrorCategoryActionResponse,
)
def revalidate_scan_error_category(
    error_type: str,
    data: ErrorCategoryActionRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    try:
        return scan_service.revalidate_error_category(
            user_id=user_id,
            error_type=error_type,
            persist_to_db=data.persist_to_db,
            progress_every=data.progress_every,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/scans/errors/{error_type}/rescan",
    response_model=ErrorCategoryActionResponse,
)
def rescan_scan_error_category(
    error_type: str,
    data: ErrorCategoryActionRequest,
    scan_service: ScanService = Depends(get_scan_service),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    try:
        return scan_service.rescan_error_category(
            user_id=user_id,
            error_type=error_type,
            persist_to_db=data.persist_to_db,
            progress_every=data.progress_every,
            model=data.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

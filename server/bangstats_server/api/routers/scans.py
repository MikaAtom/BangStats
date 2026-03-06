import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from bangstats_server.api.schemas.scans import (
    ErrorCategoryActionRequest,
    ErrorCategoryActionResponse,
    ErrorCorrectionRequest,
    ErrorCorrectionResponse,
    ErrorDetailResponse,
    ErrorListResponse,
    ImportJsonFolderRequest,
    ScanCapabilitiesResponse,
    ScanResponse,
)
from bangstats_server.core.services.scan import ScanService

router = APIRouter()


@router.post("/scans", response_model=ScanResponse)
def create_scan(
    user_id: int = Form(...),
    files: list[UploadFile] = File(...),
    parallel_workers: int | None = Form(default=None),
    keys_per_worker: int | None = Form(default=None),
):
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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


@router.get("/scans/capabilities", response_model=ScanCapabilitiesResponse)
def get_scan_capabilities():
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return scan_service.get_scan_capabilities()


@router.post("/scans/import-json-folder", response_model=ScanResponse)
def import_json_folder(data: ImportJsonFolderRequest):
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        return scan_service.import_json_folder(
            folder_path=data.folder_path,
            user_id=data.user_id,
            persist_to_db=data.persist_to_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scans/errors", response_model=ErrorListResponse)
def list_scan_errors():
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return scan_service.list_error_files()


@router.get("/scans/errors/{error_type}/{json_filename}", response_model=ErrorDetailResponse)
def get_scan_error_detail(error_type: str, json_filename: str):
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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
def correct_scan_error(error_type: str, json_filename: str, data: ErrorCorrectionRequest):
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        return scan_service.correct_error_file(
            user_id=data.user_id,
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
def revalidate_scan_error_category(error_type: str, data: ErrorCategoryActionRequest):
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        return scan_service.revalidate_error_category(
            user_id=data.user_id,
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
def rescan_scan_error_category(error_type: str, data: ErrorCategoryActionRequest):
    try:
        scan_service = ScanService()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        return scan_service.rescan_error_category(
            user_id=data.user_id,
            error_type=error_type,
            persist_to_db=data.persist_to_db,
            progress_every=data.progress_every,
            model=data.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from bangstats_server.core.services.scan import ScanService

router = APIRouter()


@router.post("/scans")
def create_scan(
    user_id: int = Form(...),
    files: list[UploadFile] = File(...),
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

        result = scan_service.scan_images(
            images_folder=tmp_dir,
            image_list=sorted(filenames),
            user_id=user_id,
            persist_to_db=True,
        )
        return result

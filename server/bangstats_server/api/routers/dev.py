from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from bangstats_server.api.dependencies import assert_user_scope, get_current_user
from bangstats_server.core.adapters.ocr.fake import FakeScannerService, generate_spread_timestamps
from bangstats_server.core.config import (
    DEV_SIMULATE_SCREENSHOT_LOCATIONS,
    DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT,
    DEV_SIMULATED_SERVER_FOLDER_ROOT,
    FAKE_SCAN_DELAY_MS,
    FAKE_SCAN_ERROR_RATE,
    FAKE_SCAN_ERROR_WEIGHTS,
    FAKE_SCAN_PROFILE,
    FAKE_SCAN_SEED,
    FAKE_TIME_SPAN_DAYS,
    REMOTE_DATA_PROVIDER,
)
from bangstats_server.core.db.models.user import User
from bangstats_server.core.services.dev_simulation import DevSimulationService
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.validation import ValidationResult, ValidationService

router = APIRouter()


class DevSeedRequest(BaseModel):
    user_id: int = Field(ge=1)
    count: int = Field(default=100, ge=1, le=10000)
    time_span_days: int = Field(default=FAKE_TIME_SPAN_DAYS, ge=1, le=3650)


class DevSeedResponse(BaseModel):
    seeded: int
    attempted: int
    requested: int


class DevConfigResponse(BaseModel):
    fake_scan_delay_ms: int
    fake_scan_error_rate: int
    fake_scan_error_weights: str
    fake_scan_profile: str
    fake_scan_seed: str
    fake_time_span_days: int
    remote_data_provider: str
    dev_simulate_screenshot_locations: bool
    dev_simulated_server_folder_root: str
    dev_simulated_client_upload_source_root: str


class DevPrepareRequest(BaseModel):
    user_id: int = Field(ge=1)
    target: Literal["local", "server", "both"] = "both"
    count: int = Field(default=20, ge=1, le=10000)
    time_span_days: int = Field(default=FAKE_TIME_SPAN_DAYS, ge=1, le=3650)
    clear_existing: bool = True


class DevPrepareResponse(BaseModel):
    local_path: str | None = None
    local_created: int | None = None
    local_existing_before: int | None = None
    server_path: str | None = None
    server_created: int | None = None
    server_existing_before: int | None = None


def _build_screenshot_payload(
    *,
    user_id: int,
    filename: str,
    scan_result: dict[str, Any],
    resolved_song_id: int,
    timestamp: datetime,
) -> dict[str, Any]:
    perfect = int(scan_result.get("perfect", 0))
    great = int(scan_result.get("great", 0))
    good = int(scan_result.get("good", 0))
    bad = int(scan_result.get("bad", 0))
    miss = int(scan_result.get("miss", 0))
    max_combo = int(scan_result.get("max_combo", 0))
    score = int(scan_result.get("score", 0))
    return {
        "user_id": user_id,
        "score": score,
        "high_score": int(scan_result.get("high_score", -1)),
        "is_new_record": bool(scan_result.get("is_new_record", False)),
        "score_rank": str(scan_result.get("score_rank", "-1")),
        "live_type": str(scan_result.get("live_type", "")).lower(),
        "free_live_data": (
            scan_result.get("free_live_data")
            if isinstance(scan_result.get("free_live_data"), dict)
            else None
        ),
        "team_live_data": (
            scan_result.get("team_live_data")
            if isinstance(scan_result.get("team_live_data"), dict)
            else None
        ),
        "perfect": perfect,
        "great": great,
        "good": good,
        "bad": bad,
        "miss": miss,
        "fast": int(scan_result.get("fast", -1)),
        "slow": int(scan_result.get("slow", -1)),
        "max_combo": max_combo,
        "full_combo": (good + bad + miss == 0),
        "all_perfect": (great + good + bad + miss == 0),
        "song_id": resolved_song_id,
        "difficulty": str(scan_result.get("difficulty", "")).lower(),
        "anomaly": False,
        "filename": filename,
        "timestamp": timestamp,
    }


@router.get("/dev/config", response_model=DevConfigResponse)
def get_dev_config(_: User = Depends(get_current_user)):
    return DevConfigResponse(
        fake_scan_delay_ms=FAKE_SCAN_DELAY_MS,
        fake_scan_error_rate=FAKE_SCAN_ERROR_RATE,
        fake_scan_error_weights=FAKE_SCAN_ERROR_WEIGHTS,
        fake_scan_profile=FAKE_SCAN_PROFILE,
        fake_scan_seed=FAKE_SCAN_SEED,
        fake_time_span_days=FAKE_TIME_SPAN_DAYS,
        remote_data_provider=REMOTE_DATA_PROVIDER,
        dev_simulate_screenshot_locations=DEV_SIMULATE_SCREENSHOT_LOCATIONS,
        dev_simulated_server_folder_root=str(DEV_SIMULATED_SERVER_FOLDER_ROOT),
        dev_simulated_client_upload_source_root=str(DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT),
    )


@router.post("/dev/seed", response_model=DevSeedResponse)
def seed_fake_screenshots(
    data: DevSeedRequest,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    scanner = FakeScannerService()
    validator = ValidationService()
    screenshot_service = ScreenshotService()

    seeded = 0
    attempted = 0
    max_attempts = max(data.count * 5, data.count)
    generated_timestamps = generate_spread_timestamps(
        max_attempts,
        data.time_span_days,
        scanner._rng,
    )

    while seeded < data.count and attempted < max_attempts:
        timestamp = generated_timestamps[attempted]
        attempted += 1
        filename = f"Screenshot_{int(timestamp.timestamp() * 1000)}.png"
        try:
            scan_result = scanner.generate_response("fake", "fake", filename)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Fake scanner failed: {exc}") from exc

        validation_output = validator.validate(filename, scan_result)
        if not isinstance(validation_output, ValidationResult):
            continue
        if not validation_output.is_valid or validation_output.resolved_song_id is None:
            continue

        payload = _build_screenshot_payload(
            user_id=user_id,
            filename=filename,
            scan_result=scan_result,
            resolved_song_id=int(validation_output.resolved_song_id),
            timestamp=timestamp,
        )
        created = screenshot_service.create_screenshot(payload)
        if created is None:
            continue
        seeded += 1

    return DevSeedResponse(seeded=seeded, attempted=attempted, requested=data.count)


@router.post("/dev/prepare-simulated-folders", response_model=DevPrepareResponse)
def prepare_simulated_folders(
    data: DevPrepareRequest,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(data.user_id, current_user)
    simulation_service = DevSimulationService()
    if not simulation_service.enabled:
        raise HTTPException(
            status_code=400,
            detail="Simulated screenshot locations are disabled for this environment.",
        )

    response = DevPrepareResponse()
    if data.target in {"local", "both"}:
        local_folder = simulation_service.user_local_source_folder(user_id, create=True)
        local_existing_before, local_created = simulation_service.prepare_folder(
            local_folder,
            count=data.count,
            time_span_days=data.time_span_days,
            clear_existing=data.clear_existing,
        )
        response.local_path = str(local_folder.resolve())
        response.local_existing_before = local_existing_before
        response.local_created = local_created

    if data.target in {"server", "both"}:
        server_folder = simulation_service.user_server_folder(user_id, create=True)
        server_existing_before, server_created = simulation_service.prepare_folder(
            server_folder,
            count=data.count,
            time_span_days=data.time_span_days,
            clear_existing=data.clear_existing,
        )
        response.server_path = str(server_folder.resolve())
        response.server_existing_before = server_existing_before
        response.server_created = server_created

    return response

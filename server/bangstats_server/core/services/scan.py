import os
import re
import json
import shutil
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from typing import Callable, List, Dict, Any, Optional

from bangstats_server.core.config import (
    EVENT_TYPE_TO_LIVE_TYPES,
    GEMINI_MODEL,
    OCR_PROVIDER,
    OLLAMA_MODEL,
    PROMPTS_PATH,
    SCAN_CACHE_ERRORS,
    SCAN_CACHE_FAST_SLOW_ERRORS,
    SCAN_CACHE_LIVE_ERRORS,
    SCAN_CACHE_MAX_COMBO_ERRORS,
    SCAN_CACHE_NOT_FOUND_ERRORS,
    SCAN_CACHE_NOTE_ERRORS,
    SCAN_CACHE_SUCCESSFUL,
)
from bangstats_server.core.scripts.prompt_generate import prompt_generate
from bangstats_server.core.adapters.ocr import get_ocr_service
from bangstats_server.core.adapters.ocr.gemini import GoogleModelService
from bangstats_server.core.config import GOOGLE_API_KEY
from bangstats_server.core.timestamps import extract_timestamp_from_filename

from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.validation import ValidationService
from bangstats_server.core.services.validation import ValidationResult


class ScanService:
    """Service for scanning images and validating results with error categorization."""

    def __init__(self):
        # load working prompt from file
        with open(PROMPTS_PATH / "prompt_full.txt", "r", encoding="utf-8") as f:
            self.working_prompt = f.read()

        self.cache_successful = SCAN_CACHE_SUCCESSFUL
        self.cache_errors = SCAN_CACHE_ERRORS
        self.cache_error_note = SCAN_CACHE_NOTE_ERRORS
        self.cache_error_not_found = SCAN_CACHE_NOT_FOUND_ERRORS
        self.cache_error_fast_slow = SCAN_CACHE_FAST_SLOW_ERRORS
        self.cache_error_max_combo = SCAN_CACHE_MAX_COMBO_ERRORS
        self.cache_error_live = SCAN_CACHE_LIVE_ERRORS
        self._setup_cache_structure()

        self.event_type_to_live_types = EVENT_TYPE_TO_LIVE_TYPES

        self.event_service = EventService()
        self.screenshot_service = ScreenshotService()
        self.ocr_provider = OCR_PROVIDER
        self.ocr_service = None
        self._ocr_init_error: Optional[str] = None
        try:
            self.ocr_service = get_ocr_service(self.ocr_provider)
        except Exception as exc:
            # OCR is required only for image scanning, not for JSON import/correction.
            self._ocr_init_error = str(exc)
            logger.warning(f"OCR service unavailable at startup: {exc}")
        self.default_model = GEMINI_MODEL if self.ocr_provider == "gemini" else OLLAMA_MODEL
        self.validation_service = ValidationService()

    def _get_available_google_keys(self) -> List[str]:
        raw = GOOGLE_API_KEY
        return [k.strip() for k in raw.split(",") if k.strip()]

    def get_scan_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": self.ocr_provider,
            "available_google_keys": len(self._get_available_google_keys()),
        }

    def compute_filename_diff(self, *, user_id: int, filenames: List[str]) -> Dict[str, Any]:
        requested = [Path(name).name for name in filenames if isinstance(name, str) and name]
        if not requested:
            return {
                "requested_total": 0,
                "already_scanned_count": 0,
                "to_scan_count": 0,
                "already_scanned_filenames": [],
                "to_scan_filenames": [],
            }

        existing = set(self.screenshot_service.get_existing_filenames_for_user(user_id, requested))
        already_scanned = [name for name in requested if name in existing]
        to_scan = [name for name in requested if name not in existing]
        return {
            "requested_total": len(requested),
            "already_scanned_count": len(already_scanned),
            "to_scan_count": len(to_scan),
            "already_scanned_filenames": already_scanned,
            "to_scan_filenames": to_scan,
        }

    def check_local_scan_path(self, folder_path: str) -> Dict[str, Any]:
        if not folder_path or not str(folder_path).strip():
            return {"is_local": False, "canonical_path": None}
        try:
            candidate = Path(folder_path).expanduser().resolve()
        except Exception:
            return {"is_local": False, "canonical_path": None}

        if candidate.exists() and candidate.is_dir():
            return {"is_local": True, "canonical_path": str(candidate)}
        return {"is_local": False, "canonical_path": None}

    def scan_local_folder(
        self,
        *,
        user_id: int,
        folder_path: str,
        filenames: List[str],
        parallel_workers: int | None = None,
        keys_per_worker: int | None = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_every: int = 10,
    ) -> Dict[str, Any]:
        locality = self.check_local_scan_path(folder_path)
        if not locality["is_local"] or not locality["canonical_path"]:
            raise ValueError("Provided folder path is not accessible on this server.")

        base_folder = Path(str(locality["canonical_path"]))
        allowed_suffixes = {".png", ".jpg", ".jpeg", ".heic", ".heif"}
        requested = [Path(name).name for name in filenames if isinstance(name, str) and name]
        image_list: List[str] = []

        if requested:
            for name in requested:
                path = base_folder / name
                if path.exists() and path.is_file() and path.suffix.lower() in allowed_suffixes:
                    image_list.append(name)
        else:
            image_list = sorted(
                [
                    path.name
                    for path in base_folder.iterdir()
                    if path.is_file() and path.suffix.lower() in allowed_suffixes
                ]
            )

        if not image_list:
            return self._init_results() | {"additional": {"provider": self.ocr_provider}}

        return self.scan_images(
            images_folder=str(base_folder),
            image_list=image_list,
            user_id=user_id,
            persist_to_db=True,
            parallel_workers=parallel_workers,
            keys_per_worker=keys_per_worker,
            on_progress=on_progress,
            progress_every=progress_every,
        )

    def _setup_cache_structure(self):
        """Setup cache folder structure."""
        folders = [
            self.cache_successful,
            self.cache_errors,
            self.cache_error_note,
            self.cache_error_not_found,
            self.cache_error_fast_slow,
            self.cache_error_max_combo,
            self.cache_error_live,
        ]

        for folder in folders:
            os.makedirs(folder, exist_ok=True)
        logger.debug("Cache structure setup complete")

    def _scan_single_image(
        self,
        image_path: str,
        model: str,
        ocr_service_override: Any = None,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Scan a single image using AI model."""
        try:
            active_ocr_service = ocr_service_override or self.ocr_service
            if active_ocr_service is None:
                try:
                    self.ocr_service = get_ocr_service(self.ocr_provider)
                    self._ocr_init_error = None
                    active_ocr_service = self.ocr_service
                except Exception as exc:
                    message = str(exc)
                    self._ocr_init_error = message
                    if "GOOGLE_API_KEY is not set" in message:
                        return None, "GOOGLE_API_KEY not configured"
                    return None, f"OCR unavailable: {message}"

            # Extract timestamp from filename for event context
            filename = os.path.basename(image_path)
            timestamp = self._extract_timestamp_from_filename(filename)

            # Get current event and generate appropriate prompt
            prompt = self._generate_prompt_for_timestamp(timestamp)

            # Use AI model to scan image
            response = active_ocr_service.generate_response(model, prompt, image_path)

            if not response:
                logger.warning(f"Empty response for image: {filename}")
                return None, "OCR returned empty result"

            return response, None

        except Exception as e:
            logger.error(f"Error scanning image {image_path}: {e}")
            message = str(e).lower()
            if "google_api_key is not set" in message:
                return None, "GOOGLE_API_KEY not configured"
            if "429" in message or "quota" in message or "rate limit" in message:
                return None, "Rate limit hit. Check key rotation and retry later."
            if "connection" in message or "timeout" in message or "network" in message:
                return None, "Network error. Check your connection and OCR endpoint."
            if "ollama request failed" in message:
                return None, "Ollama request failed. Is Ollama running?"
            return None, f"OCR failed: {e}"

    def _extract_timestamp_from_filename(self, filename: str) -> Optional[int]:
        """Extract timestamp from screenshot filename."""
        return extract_timestamp_from_filename(filename)

    def _generate_prompt_for_timestamp(self, timestamp: Optional[int]) -> str:
        """Generate context-aware prompt based on timestamp."""
        if not timestamp:
            # Timestamp may be absent for non-Screenshot naming schemes.
            return prompt_generate(["free live", "multi live"], self.working_prompt)

        # Get event at timestamp to determine available live types
        event = self.event_service.search_events_by_date(timestamp)
        if not event:
            possible_live_types = ["free live", "multi live"]
        else:
            possible_live_types = self.event_type_to_live_types.get(
                event.event_type, ["free live", "multi live"]
            )

        return prompt_generate(possible_live_types, self.working_prompt)

    def _store_result(
        self,
        filename: str,
        image_path: Optional[str],
        scan_result: Dict[str, Any],
        error_type: Optional[str],
    ) -> str:
        """Store scan result and organize files."""
        # Determine target folder
        if error_type:
            target_folder = os.path.join(self.cache_errors, error_type)
            os.makedirs(target_folder, exist_ok=True)
            # Copy image to target folder when source image exists
            if image_path and os.path.exists(image_path):
                target_image_path = os.path.join(target_folder, filename)
                shutil.copy2(image_path, target_image_path)
        else:
            target_folder = self.cache_successful

        # Save JSON result
        json_filename = os.path.splitext(filename)[0] + ".json"
        json_path = os.path.join(target_folder, json_filename)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(scan_result, f, indent=2, ensure_ascii=False)

        logger.debug(f"Stored result for {filename} in {target_folder}")
        return str(target_folder)

    def _init_results(self) -> Dict[str, Any]:
        return {
            "total_scanned": 0,
            "successful": 0,
            "errors": {
                "note_errors": 0,
                "not_found_errors": 0,
                "fast_slow_errors": 0,
                "max_combo_errors": 0,
                "live_errors": 0,
                "validation_errors": 0,
            },
            "error_files": {
                "note_errors": [],
                "not_found_errors": [],
                "fast_slow_errors": [],
                "max_combo_errors": [],
                "live_errors": [],
                "validation_errors": [],
            },
            "error_rate": 0.0,
            "validated": 0,
            "persisted": 0,
            "failed_to_persist": 0,
            "skipped_duplicates": 0,
        }

    def _split_image_list(self, image_list: List[str], workers: int) -> List[List[str]]:
        if workers <= 0:
            return []
        n = len(image_list)
        base = n // workers
        rem = n % workers
        chunks: List[List[str]] = []
        cursor = 0
        for idx in range(workers):
            size = base + (1 if idx < rem else 0)
            chunks.append(image_list[cursor : cursor + size])
            cursor += size
        return [chunk for chunk in chunks if chunk]

    def _validate_parallel_mode(
        self,
        *,
        parallel_workers: int,
        keys_per_worker: int,
    ) -> List[str]:
        if self.ocr_provider != "gemini":
            raise ValueError("Parallel key mode is supported only for OCR_PROVIDER=gemini.")

        if parallel_workers <= 0 or keys_per_worker <= 0:
            raise ValueError("parallel_workers and keys_per_worker must be positive integers.")

        available_keys = self._get_available_google_keys()
        if not available_keys:
            raise ValueError("No Google API keys available for parallel scanning.")

        requested_total = parallel_workers * keys_per_worker
        if requested_total > len(available_keys):
            raise ValueError(
                f"Requested {requested_total} keys ({parallel_workers}x{keys_per_worker}) "
                f"but only {len(available_keys)} keys available."
            )
        return available_keys[:requested_total]

    def _scan_images_worker(
        self,
        *,
        images_folder: str,
        image_list: List[str],
        model: str,
        user_id: Optional[int],
        persist_to_db: bool,
        worker_keys: List[str],
    ) -> Dict[str, Any]:
        worker_service = ScanService()
        worker_service.ocr_service = GoogleModelService(api_keys=worker_keys)
        worker_service._ocr_init_error = None
        return worker_service.scan_images(
            images_folder=images_folder,
            image_list=image_list,
            model=model,
            user_id=user_id,
            persist_to_db=persist_to_db,
        )

    def _merge_scan_results(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        scalar_keys = [
            "total_scanned",
            "successful",
            "validated",
            "persisted",
            "failed_to_persist",
            "skipped_duplicates",
        ]
        for key in scalar_keys:
            target[key] += source.get(key, 0)

        for err_type, count in source.get("errors", {}).items():
            target["errors"].setdefault(err_type, 0)
            target["errors"][err_type] += count

        for err_type, files in source.get("error_files", {}).items():
            target["error_files"].setdefault(err_type, [])
            target["error_files"][err_type].extend(files)

    def _canonical_image_filename(self, source_filename: str) -> str:
        return f"{Path(source_filename).stem}.png"

    def _list_error_json_paths(self, error_type: str) -> List[Path]:
        error_dir = Path(self.cache_errors) / error_type
        if not error_dir.exists() or not error_dir.is_dir():
            return []
        return sorted(
            [
                path
                for path in error_dir.glob("*.json")
                if path.is_file() and not path.name.endswith(".validation.json")
            ]
        )

    def _find_error_image_path(self, error_type: str, json_filename: str) -> Optional[Path]:
        error_dir = Path(self.cache_errors) / error_type
        stem = Path(json_filename).stem
        candidates = [
            error_dir / f"{stem}.png",
            error_dir / f"{stem}.jpg",
            error_dir / f"{stem}.jpeg",
            error_dir / f"{stem}.heic",
            error_dir / f"{stem}.heif",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _persist_validated_payload(
        self,
        *,
        user_id: int,
        image_filename: str,
        payload: Dict[str, Any],
        validation_output: Any,
    ) -> Dict[str, bool]:
        result = {
            "persisted": False,
            "skipped_duplicates": False,
            "failed_to_persist": False,
        }
        resolved_song_id = self._extract_resolved_song_id(validation_output)
        if resolved_song_id is None:
            result["failed_to_persist"] = True
            return result
        try:
            timestamp_ms = self._extract_timestamp_from_filename(image_filename)
            screenshot_payload = self._build_screenshot_payload(
                user_id=user_id,
                filename=image_filename,
                scan_result=payload,
                resolved_song_id=resolved_song_id,
                timestamp_ms=timestamp_ms,
            )
            created = self.screenshot_service.create_screenshot(screenshot_payload)
            if created is None:
                result["skipped_duplicates"] = True
            else:
                result["persisted"] = True
        except Exception as exc:
            logger.error(f"Failed to persist validated payload for {image_filename}: {exc}")
            result["failed_to_persist"] = True
        return result

    def _init_category_action_results(self, total_files: int) -> Dict[str, Any]:
        return {
            "total_files": total_files,
            "processed": 0,
            "successful": 0,
            "persisted": 0,
            "skipped_duplicates": 0,
            "failed_to_persist": 0,
            "missing_image": 0,
            "scan_failed": 0,
            "errors": {},
        }

    def _remove_error_entry(self, error_type: str, json_filename: str) -> None:
        error_dir = Path(self.cache_errors) / error_type
        json_path = error_dir / json_filename
        validation_path = error_dir / f"{Path(json_filename).stem}.validation.json"
        image_candidates = [
            error_dir / f"{Path(json_filename).stem}.png",
            error_dir / f"{Path(json_filename).stem}.jpg",
            error_dir / f"{Path(json_filename).stem}.jpeg",
            error_dir / f"{Path(json_filename).stem}.heic",
            error_dir / f"{Path(json_filename).stem}.heif",
        ]

        for candidate in [json_path, validation_path, *image_candidates]:
            if candidate.exists():
                candidate.unlink()

    def _resolve_error_json_path(self, error_type: str, json_filename: str) -> Path:
        if not error_type:
            raise ValueError("error_type is required")
        filename = Path(json_filename).name
        if not filename.endswith(".json"):
            filename = f"{Path(filename).stem}.json"
        path = Path(self.cache_errors) / error_type / filename
        if not path.exists():
            raise FileNotFoundError(f"Error JSON not found: {path}")
        return path

    def list_error_files(self) -> Dict[str, Any]:
        errors_root = Path(self.cache_errors)
        summary: Dict[str, int] = {}
        files: Dict[str, List[str]] = {}
        total = 0

        if not errors_root.exists():
            return {"total": 0, "errors": summary, "error_files": files}

        for error_dir in sorted([p for p in errors_root.iterdir() if p.is_dir()]):
            names = sorted(
                [
                    path.name
                    for path in error_dir.glob("*.json")
                    if not path.name.endswith(".validation.json")
                ]
            )
            summary[error_dir.name] = len(names)
            files[error_dir.name] = names
            total += len(names)

        return {"total": total, "errors": summary, "error_files": files}

    def get_error_detail(self, error_type: str, json_filename: str) -> Dict[str, Any]:
        json_path = self._resolve_error_json_path(error_type, json_filename)
        validation_path = json_path.with_name(f"{json_path.stem}.validation.json")

        with open(json_path, "r", encoding="utf-8") as fh:
            scan_data = json.load(fh)

        validation_data = None
        if validation_path.exists():
            with open(validation_path, "r", encoding="utf-8") as fh:
                validation_data = json.load(fh)

        return {
            "error_type": error_type,
            "json_filename": json_path.name,
            "image_filename": self._canonical_image_filename(json_path.name),
            "scan_data": scan_data,
            "validation": validation_data,
        }

    def correct_error_file(
        self,
        *,
        user_id: int,
        error_type: str,
        json_filename: str,
        corrected_scan_data: Dict[str, Any],
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        json_path = self._resolve_error_json_path(error_type, json_filename)
        canonical_filename = self._canonical_image_filename(json_path.name)
        validation_output = self.validation_service.validate(canonical_filename, corrected_scan_data)
        new_error_type = self._extract_error_type(validation_output)

        # Remove stale entry before rewriting it to the latest category.
        self._remove_error_entry(error_type, json_path.name)
        target_folder = self._store_result(
            filename=canonical_filename,
            image_path=None,
            scan_result=corrected_scan_data,
            error_type=new_error_type,
        )
        self._store_validation_artifact(canonical_filename, target_folder, validation_output)

        persisted = False
        skipped_duplicate = False
        failed_to_persist = False
        resolved_song_id = self._extract_resolved_song_id(validation_output)
        if new_error_type is None and persist_to_db:
            if resolved_song_id is None:
                failed_to_persist = True
            else:
                try:
                    timestamp_ms = self._extract_timestamp_from_filename(canonical_filename)
                    payload = self._build_screenshot_payload(
                        user_id=user_id,
                        filename=canonical_filename,
                        scan_result=corrected_scan_data,
                        resolved_song_id=resolved_song_id,
                        timestamp_ms=timestamp_ms,
                    )
                    created = self.screenshot_service.create_screenshot(payload)
                    if created is None:
                        skipped_duplicate = True
                    else:
                        persisted = True
                except Exception:
                    failed_to_persist = True

        return {
            "image_filename": canonical_filename,
            "is_valid": new_error_type is None,
            "error_type": new_error_type,
            "persisted": persisted,
            "skipped_duplicates": skipped_duplicate,
            "failed_to_persist": failed_to_persist,
        }

    def revalidate_error_category(
        self,
        *,
        user_id: int,
        error_type: str,
        persist_to_db: bool = True,
        progress_every: int = 500,
    ) -> Dict[str, Any]:
        if progress_every <= 0:
            raise ValueError("progress_every must be greater than 0")

        json_files = self._list_error_json_paths(error_type)
        results = self._init_category_action_results(total_files=len(json_files))

        for json_path in json_files:
            try:
                with open(json_path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                if not isinstance(payload, dict):
                    raise ValueError("JSON payload must be an object")
            except Exception as exc:
                logger.warning(f"Failed to load error JSON {json_path.name}: {exc}")
                results["processed"] += 1
                results["errors"]["validation_errors"] = (
                    results["errors"].get("validation_errors", 0) + 1
                )
                continue

            image_filename = self._canonical_image_filename(json_path.name)
            validation_output = self.validation_service.validate(image_filename, payload)
            new_error_type = self._extract_error_type(validation_output)

            self._remove_error_entry(error_type, json_path.name)
            target_folder = self._store_result(
                filename=image_filename,
                image_path=None,
                scan_result=payload,
                error_type=new_error_type,
            )
            self._store_validation_artifact(image_filename, target_folder, validation_output)

            results["processed"] += 1
            if new_error_type is None:
                results["successful"] += 1
                if persist_to_db:
                    persist_result = self._persist_validated_payload(
                        user_id=user_id,
                        image_filename=image_filename,
                        payload=payload,
                        validation_output=validation_output,
                    )
                    if persist_result["persisted"]:
                        results["persisted"] += 1
                    if persist_result["skipped_duplicates"]:
                        results["skipped_duplicates"] += 1
                    if persist_result["failed_to_persist"]:
                        results["failed_to_persist"] += 1
            else:
                results["errors"][new_error_type] = results["errors"].get(new_error_type, 0) + 1

            if results["processed"] % progress_every == 0:
                print(f"Revalidate progress: {results['processed']}/{results['total_files']}")

        return results

    def rescan_error_category(
        self,
        *,
        user_id: int,
        error_type: str,
        persist_to_db: bool = True,
        progress_every: int = 500,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        if progress_every <= 0:
            raise ValueError("progress_every must be greater than 0")

        json_files = self._list_error_json_paths(error_type)
        results = self._init_category_action_results(total_files=len(json_files))
        selected_model = model or self.default_model

        for json_path in json_files:
            image_filename = self._canonical_image_filename(json_path.name)
            image_path = self._find_error_image_path(error_type, json_path.name)
            if image_path is None:
                results["processed"] += 1
                results["missing_image"] += 1
                if results["processed"] % progress_every == 0:
                    print(f"Rescan progress: {results['processed']}/{results['total_files']}")
                continue

            scan_result, scan_error = self._scan_single_image(str(image_path), selected_model)
            if not scan_result:
                logger.warning(f"Failed to rescan {image_filename}: {scan_error or 'unknown error'}")
                results["processed"] += 1
                results["scan_failed"] += 1
                if results["processed"] % progress_every == 0:
                    print(f"Rescan progress: {results['processed']}/{results['total_files']}")
                continue

            validation_output = self.validation_service.validate(image_filename, scan_result)
            new_error_type = self._extract_error_type(validation_output)

            target_folder = self._store_result(
                filename=image_filename,
                image_path=str(image_path),
                scan_result=scan_result,
                error_type=new_error_type,
            )
            self._store_validation_artifact(image_filename, target_folder, validation_output)
            if new_error_type != error_type:
                self._remove_error_entry(error_type, json_path.name)

            results["processed"] += 1
            if new_error_type is None:
                results["successful"] += 1
                if persist_to_db:
                    persist_result = self._persist_validated_payload(
                        user_id=user_id,
                        image_filename=image_filename,
                        payload=scan_result,
                        validation_output=validation_output,
                    )
                    if persist_result["persisted"]:
                        results["persisted"] += 1
                    if persist_result["skipped_duplicates"]:
                        results["skipped_duplicates"] += 1
                    if persist_result["failed_to_persist"]:
                        results["failed_to_persist"] += 1
            else:
                results["errors"][new_error_type] = results["errors"].get(new_error_type, 0) + 1

            if results["processed"] % progress_every == 0:
                print(f"Rescan progress: {results['processed']}/{results['total_files']}")

        return results

    def import_json_folder(
        self,
        *,
        folder_path: str,
        user_id: int,
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        source = Path(folder_path).expanduser()
        if not source.exists() or not source.is_dir():
            raise ValueError(f"JSON folder does not exist: {source}")

        json_files = sorted(
            [
                path
                for path in source.glob("*.json")
                if path.is_file() and not path.name.endswith(".validation.json")
            ]
        )
        results = self._init_results()
        logger.info(
            "Starting JSON import for {} files from {}",
            len(json_files),
            source,
        )

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                if not isinstance(payload, dict):
                    raise ValueError("JSON payload must be an object")
            except Exception as exc:
                logger.warning(f"Failed to load {json_file.name}: {exc}")
                results["total_scanned"] += 1
                results["errors"]["validation_errors"] += 1
                results["error_files"]["validation_errors"].append(
                    self._canonical_image_filename(json_file.name)
                )
                continue

            image_filename = self._canonical_image_filename(json_file.name)
            validation_output = self.validation_service.validate(image_filename, payload)
            error_type = self._extract_error_type(validation_output)
            target_folder = self._store_result(image_filename, None, payload, error_type)
            self._store_validation_artifact(image_filename, target_folder, validation_output)

            results["total_scanned"] += 1
            if error_type:
                results["errors"].setdefault(error_type, 0)
                results["error_files"].setdefault(error_type, [])
                results["errors"][error_type] += 1
                results["error_files"][error_type].append(image_filename)
                continue

            results["successful"] += 1
            results["validated"] += 1
            if not persist_to_db:
                continue

            resolved_song_id = self._extract_resolved_song_id(validation_output)
            if resolved_song_id is None:
                results["failed_to_persist"] += 1
                continue

            try:
                timestamp_ms = self._extract_timestamp_from_filename(image_filename)
                screenshot_payload = self._build_screenshot_payload(
                    user_id=user_id,
                    filename=image_filename,
                    scan_result=payload,
                    resolved_song_id=resolved_song_id,
                    timestamp_ms=timestamp_ms,
                )
                created = self.screenshot_service.create_screenshot(screenshot_payload)
                if created is None:
                    results["skipped_duplicates"] += 1
                else:
                    results["persisted"] += 1
            except Exception as persist_error:
                logger.error(
                    f"Failed to persist imported screenshot for {image_filename}: {persist_error}"
                )
                results["failed_to_persist"] += 1

        error_count = sum(results["errors"].values())
        results["error_rate"] = (
            round((error_count / results["total_scanned"]) * 100, 2)
            if results["total_scanned"]
            else 0.0
        )
        logger.info(
            "JSON import complete: processed={} successful={} persisted={} duplicates={} failed_to_persist={}",
            results["total_scanned"],
            results["successful"],
            results["persisted"],
            results["skipped_duplicates"],
            results["failed_to_persist"],
        )
        return results

    def _store_validation_artifact(
        self,
        filename: str,
        target_folder: Optional[str],
        validation_output: Any,
    ) -> None:
        if not target_folder:
            logger.warning(f"Target folder missing, skipping validation artifact for {filename}")
            return

        if isinstance(validation_output, ValidationResult):
            artifact = {
                "is_valid": validation_output.is_valid,
                "error_type": validation_output.error_type,
                "resolved_song_id": validation_output.resolved_song_id,
                "normalized": validation_output.normalized,
                "reasons": validation_output.reasons,
                "severity": validation_output.severity,
                "confidence": validation_output.confidence,
            }
        else:
            artifact = {
                "is_valid": validation_output is None,
                "error_type": str(validation_output) if validation_output is not None else None,
                "resolved_song_id": None,
                "normalized": {},
                "reasons": [],
                "severity": "error" if validation_output else "info",
                "confidence": 0.0 if validation_output else 1.0,
            }

        json_filename = os.path.splitext(filename)[0] + ".validation.json"
        json_path = os.path.join(target_folder, json_filename)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        logger.debug(f"Stored validation artifact for {filename} in {target_folder}")

    def _extract_error_type(self, validation_output: Any) -> Optional[str]:
        """Compatibility adapter for both legacy and structured validator outputs."""
        if isinstance(validation_output, ValidationResult):
            return validation_output.error_type
        if isinstance(validation_output, str):
            return validation_output
        return None

    def _extract_resolved_song_id(self, validation_output: Any) -> Optional[int]:
        if isinstance(validation_output, ValidationResult):
            return validation_output.resolved_song_id
        return None

    def _build_screenshot_payload(
        self,
        user_id: int,
        filename: str,
        scan_result: Dict[str, Any],
        resolved_song_id: int,
        timestamp_ms: Optional[int],
    ) -> Dict[str, Any]:
        timestamp = (
            datetime.datetime.fromtimestamp(timestamp_ms / 1000)
            if timestamp_ms
            else datetime.datetime.now()
        )

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

    def scan_images(
        self,
        images_folder: str,
        image_list: List[str],
        model: Optional[str] = None,
        user_id: Optional[int] = None,
        persist_to_db: bool = False,
        parallel_workers: Optional[int] = None,
        keys_per_worker: Optional[int] = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_every: int = 10,
    ) -> Dict[str, Any]:
        """
        Scan images using AI model and validate results.

        Args:
            images_folder: Path to folder containing images
            image_list: List of image filenames to scan
            model: AI model to use for scanning

        Returns:
            Dict with scan results and statistics
        """
        logger.info(f"Starting scan of {len(image_list)} images from {images_folder}")
        selected_model = model or self.default_model
        active_provider = getattr(self, "ocr_provider", OCR_PROVIDER)

        results = self._init_results()
        results["additional"] = {}

        if parallel_workers is not None or keys_per_worker is not None:
            if parallel_workers is None or keys_per_worker is None:
                raise ValueError(
                    "parallel_workers and keys_per_worker must be provided together."
                )

            selected_keys = self._validate_parallel_mode(
                parallel_workers=parallel_workers,
                keys_per_worker=keys_per_worker,
            )
            chunks = self._split_image_list(image_list, parallel_workers)
            worker_key_groups = [
                selected_keys[idx * keys_per_worker : (idx + 1) * keys_per_worker]
                for idx in range(parallel_workers)
            ]

            logger.info(
                "Parallel scan enabled: workers={} keys_per_worker={} files={}",
                parallel_workers,
                keys_per_worker,
                len(image_list),
            )

            with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                futures = []
                for idx, chunk in enumerate(chunks):
                    if idx >= len(worker_key_groups):
                        break
                    if not chunk:
                        continue
                    futures.append(
                        executor.submit(
                            self._scan_images_worker,
                            images_folder=images_folder,
                            image_list=chunk,
                            model=selected_model,
                            user_id=user_id,
                            persist_to_db=persist_to_db,
                            worker_keys=worker_key_groups[idx],
                        )
                    )

                for future in futures:
                    worker_result = future.result()
                    self._merge_scan_results(results, worker_result)
                    if on_progress:
                        on_progress(results.copy())

            error_rate = (
                (sum(results["errors"].values()) / results["total_scanned"]) * 100
                if results["total_scanned"] > 0
                else 0
            )
            results["error_rate"] = round(error_rate, 2)
            results["additional"] = {
                "provider": active_provider,
                "parallel_workers": parallel_workers,
                "keys_per_worker": keys_per_worker,
                "mode": f"{parallel_workers}x{keys_per_worker}",
                "parallel_enabled": True,
            }
            if on_progress:
                on_progress(results.copy())
            return results

        for image_file in image_list:
            image_path = os.path.join(images_folder, image_file)
            if not os.path.exists(image_path):
                logger.warning(f"Image not found: {image_path}")
                continue

            try:
                # Generate scan result
                scan_result, scan_error = self._scan_single_image(image_path, selected_model)
                if not scan_result:
                    logger.warning(
                        f"Failed to scan image: {image_file}. Reason: {scan_error or 'unknown'}"
                    )
                    print(f"Failed {image_file}: {scan_error or 'unknown error'}")
                    continue

                # Validate and categorize result
                validation_output = self.validation_service.validate(image_file, scan_result)
                error_type = self._extract_error_type(validation_output)

                # Store result and organize files
                target_folder = self._store_result(image_file, image_path, scan_result, error_type)
                self._store_validation_artifact(image_file, target_folder, validation_output)

                results["total_scanned"] += 1
                if error_type:
                    results["errors"].setdefault(error_type, 0)
                    results["error_files"].setdefault(error_type, [])
                    results["errors"][error_type] += 1
                    results["error_files"][error_type].append(image_file)
                else:
                    results["successful"] += 1
                    results["validated"] += 1
                    if persist_to_db and user_id is not None:
                        resolved_song_id = self._extract_resolved_song_id(validation_output)
                        if resolved_song_id is None:
                            results["failed_to_persist"] += 1
                            logger.warning(
                                f"Validation passed but no resolved song ID for {image_file}"
                            )
                        else:
                            try:
                                timestamp_ms = self._extract_timestamp_from_filename(image_file)
                                payload = self._build_screenshot_payload(
                                    user_id=user_id,
                                    filename=image_file,
                                    scan_result=scan_result,
                                    resolved_song_id=resolved_song_id,
                                    timestamp_ms=timestamp_ms,
                                )
                                created = self.screenshot_service.create_screenshot(payload)
                                if created is None:
                                    results["skipped_duplicates"] += 1
                                    print(f"Skipped duplicate screenshot: {image_file}")
                                else:
                                    results["persisted"] += 1
                            except Exception as persist_error:
                                results["failed_to_persist"] += 1
                                logger.error(
                                    f"Failed to persist screenshot for {image_file}: {persist_error}"
                                )

                logger.debug(f"Processed {image_file}: {error_type or 'successful'}")
                print(f"Processed {image_file}: {error_type or 'successful'}")
                if on_progress and max(1, progress_every) > 0:
                    if results["total_scanned"] % max(1, progress_every) == 0:
                        on_progress(results.copy())

            except Exception as e:
                logger.error(f"Error processing {image_file}: {e}")

        # Generate summary
        error_rate = (
            (sum(results["errors"].values()) / results["total_scanned"]) * 100
            if results["total_scanned"] > 0
            else 0
        )
        results["error_rate"] = round(error_rate, 2)
        results["additional"] = {
            "provider": active_provider,
            "parallel_enabled": False,
        }
        if on_progress:
            on_progress(results.copy())

        logger.info(
            f"Scan complete: {results['successful']} successful, {sum(results['errors'].values())} errors ({error_rate:.2f}% error rate)"
        )
        return results

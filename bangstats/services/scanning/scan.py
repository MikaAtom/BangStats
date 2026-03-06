import os
import re
import json
import shutil
import datetime
from loguru import logger
from typing import List, Dict, Any, Optional

from bangstats.config import (
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
from scripts.prompt_generate import prompt_generate
from bangstats.adapters.ocr import get_ocr_service

from bangstats.services.data.event import EventService
from bangstats.services.data.screenshot import ScreenshotService
from bangstats.services.scanning.validation import ValidationService
from bangstats.services.scanning.validation import ValidationResult


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
        self.ocr_service = get_ocr_service(self.ocr_provider)
        self.default_model = GEMINI_MODEL if self.ocr_provider == "gemini" else OLLAMA_MODEL
        self.validation_service = ValidationService()

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
        self, image_path: str, model: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Scan a single image using AI model."""
        try:
            # Extract timestamp from filename for event context
            filename = os.path.basename(image_path)
            timestamp = self._extract_timestamp_from_filename(filename)

            # Get current event and generate appropriate prompt
            prompt = self._generate_prompt_for_timestamp(timestamp)

            # Use AI model to scan image
            response = self.ocr_service.generate_response(model, prompt, image_path)

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
        match = re.search(r"Screenshot_(\d{8})[-_](\d{6})", filename)
        if not match:
            logger.warning(f"Could not extract timestamp from filename: {filename}")
            return None

        date_part = match.group(1)  # YYYYMMDD
        time_part = match.group(2)  # HHMMSS
        dt = datetime.datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
        return int(dt.timestamp() * 1000)

    def _generate_prompt_for_timestamp(self, timestamp: Optional[int]) -> str:
        """Generate context-aware prompt based on timestamp."""
        if not timestamp:
            return prompt_generate()  # Use default prompt

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
        image_path: str,
        scan_result: Dict[str, Any],
        error_type: Optional[str],
    ) -> str:
        """Store scan result and organize files."""
        # Determine target folder
        if error_type:
            target_folder = os.path.join(self.cache_errors, error_type)
            # Copy image to target folder
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

        results = {
            "total_scanned": 0,
            "successful": 0,
            "errors": {
                "note_errors": 0,
                "not_found_errors": 0,
                "fast_slow_errors": 0,
                "max_combo_errors": 0,
                "live_errors": 0,
            },
            "error_files": {
                "note_errors": [],
                "not_found_errors": [],
                "fast_slow_errors": [],
                "max_combo_errors": [],
                "live_errors": [],
            },
            "error_rate": 0.0,
            "validated": 0,
            "persisted": 0,
            "failed_to_persist": 0,
            "skipped_duplicates": 0,
        }

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

            except Exception as e:
                logger.error(f"Error processing {image_file}: {e}")

        # Generate summary
        error_rate = (
            (sum(results["errors"].values()) / results["total_scanned"]) * 100
            if results["total_scanned"] > 0
            else 0
        )
        results["error_rate"] = round(error_rate, 2)

        logger.info(
            f"Scan complete: {results['successful']} successful, {sum(results['errors'].values())} errors ({error_rate:.2f}% error rate)"
        )
        return results

import os
import re
import json
import shutil
import datetime
from loguru import logger
from typing import List, Dict, Any, Optional

from bangstats.config import config
from bangstats.scripts.prompt_generate import prompt_generate

from bangstats.services.event_service import EventService
from bangstats.services.validation_service import ValidationService
from bangstats.services.google_genai_service import GoogleModelService


class ScanService:
    """Service for scanning images and validating results with error categorization."""
    
    def __init__(self):
        prompts_path = config.get("PROMPTS_PATH")
        # load working prompt from file
        with open(prompts_path / "prompt_full.txt", "r", encoding="utf-8") as f:
            self.working_prompt = f.read()

        self.cache_successful = config.get("SCAN_DATA_CACHE_SUCCESSFUL_PATH")
        self.cache_errors = config.get("SCAN_DATA_CACHE_ERRORS_PATH")
        self.cache_error_note = config.get("SCAN_DATA_CACHE_NOTE_ERRORS_PATH")
        self.cache_error_not_found = config.get("SCAN_DATA_CACHE_NOT_FOUND_ERRORS_PATH")
        self.cache_error_fast_slow = config.get("SCAN_DATA_CACHE_FAST_SLOW_ERRORS_PATH")
        self.cache_error_max_combo = config.get("SCAN_DATA_CACHE_MAX_COMBO_ERRORS_PATH")
        self.cache_error_live = config.get("SCAN_DATA_CACHE_LIVE_ERRORS_PATH")
        self._setup_cache_structure()

        self.event_type_to_live_types = config.get("EVENT_TYPE_TO_LIVE_TYPES")

        self.event_service = EventService()
        self.google_service = GoogleModelService()
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
            self.cache_error_live
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
        logger.debug(f"Cache structure setup complete")
    
    def _scan_single_image(self, image_path: str, model: str) -> Optional[Dict[str, Any]]:
        """Scan a single image using AI model."""
        try:
            # Extract timestamp from filename for event context
            filename = os.path.basename(image_path)
            timestamp = self._extract_timestamp_from_filename(filename)
            
            # Get current event and generate appropriate prompt
            prompt = self._generate_prompt_for_timestamp(timestamp)
            
            # Use AI model to scan image
            response = self.google_service.generate_response(model, prompt, image_path)
            
            if not response:
                logger.warning(f"Empty response for image: {filename}")
                return None
                
            return response
            
        except Exception as e:
            logger.error(f"Error scanning image {image_path}: {e}")
            return None
    
    def _extract_timestamp_from_filename(self, filename: str) -> Optional[int]:
        """Extract timestamp from screenshot filename."""
        match = re.search(r'Screenshot_(\d{8})[-_](\d{6})', filename)
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
            
            possible_live_types = self.event_type_to_live_types.get(event.event_type, ["free live", "multi live"])
        
        # Generate filtered prompt (assuming prompt_generate can accept live types)
        return prompt_generate(possible_live_types, self.working_prompt)
    
    def _store_result(self, filename: str, image_path: str, scan_result: Dict[str, Any], error_type: Optional[str]):
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
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(scan_result, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Stored result for {filename} in {target_folder}")

    def scan_images(self, images_folder: str, image_list: List[str], model: str = "gemini-2.5-flash") -> Dict[str, Any]:
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
            "error_rate": 0.0
        }
        
        for image_file in image_list:
            image_path = os.path.join(images_folder, image_file)
            if not os.path.exists(image_path):
                logger.warning(f"Image not found: {image_path}")
                continue
                
            try:
                # Generate scan result
                scan_result = self._scan_single_image(image_path, model)
                if not scan_result:
                    logger.warning(f"Failed to scan image: {image_file}")
                    continue
                
                # Validate and categorize result
                error_type = self.validation_service.validate(image_file, scan_result)
                
                # Store result and organize files
                self._store_result(image_file, image_path, scan_result, error_type)
                
                results["total_scanned"] += 1
                if error_type:
                    results["errors"][error_type] += 1
                    results["error_files"][error_type].append(image_file)
                else:
                    results["successful"] += 1
                    
                logger.debug(f"Processed {image_file}: {error_type or 'successful'}")
                print(f"Processed {image_file}: {error_type or 'successful'}")
                
            except Exception as e:
                logger.error(f"Error processing {image_file}: {e}")
        
        # Generate summary
        error_rate = (sum(results["errors"].values()) / results["total_scanned"]) * 100 if results["total_scanned"] > 0 else 0
        results["error_rate"] = round(error_rate, 2)
        
        logger.info(f"Scan complete: {results['successful']} successful, {sum(results['errors'].values())} errors ({error_rate:.2f}% error rate)")
        return results
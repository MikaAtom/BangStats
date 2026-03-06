import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent

SERVERS = {
    "jp": 0,
    "en": 1,
    "tw": 2,
    "cn": 3,
    "kr": 4,
}

EVENT_TYPE_TO_LIVE_TYPES = {
    "story": ["free live", "multi live"],
    "versus": ["free live", "multi live"],
    "mission_live": ["free live", "multi live"],
    "challenge": ["free live", "multi live", "challenge live"],
    "festival": ["free live", "multi live", "team live battle"],
    "live_try": ["free live", "multi live"],
    "medley": ["free live", "multi live", "medley live"],
}

DB_PATH = PACKAGE_ROOT / "storage" / "bangstats.db"
LOGS_DIR = PACKAGE_ROOT / "storage" / "logs"
LOG_FILE_NAME = "bs_{timestamp}.log"

REMOTE_CACHE = PACKAGE_ROOT / "cache" / "remote_data_cache"

SCAN_CACHE = PACKAGE_ROOT / "cache" / "scan_data_cache"
SCAN_CACHE_SUCCESSFUL = SCAN_CACHE / "successful"
SCAN_CACHE_ERRORS = SCAN_CACHE / "errors"
SCAN_CACHE_NOTE_ERRORS = SCAN_CACHE_ERRORS / "note_errors"
SCAN_CACHE_NOT_FOUND_ERRORS = SCAN_CACHE_ERRORS / "not_found_errors"
SCAN_CACHE_FAST_SLOW_ERRORS = SCAN_CACHE_ERRORS / "fast_slow_errors"
SCAN_CACHE_MAX_COMBO_ERRORS = SCAN_CACHE_ERRORS / "max_combo_errors"
SCAN_CACHE_LIVE_ERRORS = SCAN_CACHE_ERRORS / "live_errors"

PROMPTS_PATH = PACKAGE_ROOT / "adapters" / "ocr" / "prompts"


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


OCR_PROVIDER = os.getenv("OCR_PROVIDER", "gemini").strip().lower() or "gemini"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").strip() or "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava").strip() or "llava"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

REMOTE_REQUEST_RETRIES = _get_int_env("REMOTE_REQUEST_RETRIES", 3)
REMOTE_REQUEST_TIMEOUT = _get_int_env("REMOTE_REQUEST_TIMEOUT", 10)
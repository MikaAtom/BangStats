from pathlib import Path


class Defaults:
    DEBUG = False
    TESTING = False

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

    STORAGE_DIR = "storage"
    RESOURCES_DIR = "resources"
    CACHE_DIR = "cache"

    LOGS_DIR = Path(__file__).parent.parent / STORAGE_DIR / "logs"
    LOG_FILE_NAME = "bs_{timestamp}.log"
    LOG_LEVEL = "INFO"

    DB_FILE = "bangstats.db"
    DB_PATH = Path(__file__).parent.parent / STORAGE_DIR / DB_FILE

    REMOTE_DATA_CACHE_FOLDER = "remote_data_cache"
    REMOTE_DATA_CACHE_PATH = Path(__file__).parent.parent / CACHE_DIR / REMOTE_DATA_CACHE_FOLDER
    REMOTE_REQUEST_RETRIES = 3
    REMOTE_REQUEST_TIMEOUT = 10


    SCAN_DATA_CACHE_FOLDER = "scan_data_cache"
    SCAN_DATA_CACHE_PATH = Path(__file__).parent.parent / CACHE_DIR / SCAN_DATA_CACHE_FOLDER
    SCAN_DATA_CACHE_SUCCESSFUL = "successful"
    SCAN_DATA_CACHE_ERRORS = "errors"
    SCAN_DATA_CACHE_NOTE_ERRORS = "note_errors"
    SCAN_DATA_CACHE_NOT_FOUND_ERRORS = "not_found_errors"
    SCAN_DATA_CACHE_FAST_SLOW_ERRORS = "fast_slow_errors"
    SCAN_DATA_CACHE_MAX_COMBO_ERRORS = "max_combo_errors"
    SCAN_DATA_CACHE_LIVE_ERRORS = "live_errors"

    SCAN_DATA_CACHE_SUCCESSFUL_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_SUCCESSFUL
    SCAN_DATA_CACHE_ERRORS_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_ERRORS

    SCAN_DATA_CACHE_NOTE_ERRORS_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_ERRORS / SCAN_DATA_CACHE_NOTE_ERRORS
    SCAN_DATA_CACHE_NOT_FOUND_ERRORS_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_ERRORS / SCAN_DATA_CACHE_NOT_FOUND_ERRORS
    SCAN_DATA_CACHE_FAST_SLOW_ERRORS_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_ERRORS / SCAN_DATA_CACHE_FAST_SLOW_ERRORS
    SCAN_DATA_CACHE_MAX_COMBO_ERRORS_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_ERRORS / SCAN_DATA_CACHE_MAX_COMBO_ERRORS
    SCAN_DATA_CACHE_LIVE_ERRORS_PATH = SCAN_DATA_CACHE_PATH / SCAN_DATA_CACHE_ERRORS / SCAN_DATA_CACHE_LIVE_ERRORS


    PROMPTS_FOLDER = "prompts"
    PROMPTS_PATH = Path(__file__).parent.parent / PROMPTS_FOLDER

    

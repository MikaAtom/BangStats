import os
import shutil
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CORE_ROOT.parents[2]
PACKAGE_ROOT = CORE_ROOT

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

BANGSTATS_ENV = os.getenv("BANGSTATS_ENV", "production").strip().lower() or "production"
ENV_STORAGE_ROOT = PROJECT_ROOT / "storage" / BANGSTATS_ENV

_db_path_override = os.getenv("BANGSTATS_DB_PATH", "").strip()
if _db_path_override:
    DB_PATH = Path(_db_path_override).expanduser()
else:
    DB_PATH = ENV_STORAGE_ROOT / "bangstats.db"
LOGS_DIR = ENV_STORAGE_ROOT / "logs"
LOG_FILE_NAME = "bs_{timestamp}.log"

PROMPTS_PATH = CORE_ROOT / "adapters" / "ocr" / "prompts"


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_csv_int_env(name: str) -> list[int]:
    values: list[int] = []
    for item in _get_csv_env(name):
        try:
            parsed = int(item)
        except ValueError:
            continue
        if parsed > 0 and parsed not in values:
            values.append(parsed)
    return values


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


OCR_PROVIDER = os.getenv("OCR_PROVIDER", "gemini").strip().lower() or "gemini"
REMOTE_DATA_PROVIDER = (
    os.getenv("REMOTE_DATA_PROVIDER", "bestdori").strip().lower() or "bestdori"
)
DISABLE_LEGACY_CACHE_MIGRATION = (
    os.getenv("BANGSTATS_DISABLE_LEGACY_CACHE_MIGRATION", "").strip().lower()
    in {"1", "true", "yes", "on"}
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").strip() or "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava").strip() or "llava"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

REMOTE_CACHE = ENV_STORAGE_ROOT / "cache" / "remote_data_cache"

SCAN_CACHE = ENV_STORAGE_ROOT / "cache" / "scan_data_cache"
SCAN_CACHE_SUCCESSFUL = SCAN_CACHE / "successful"
SCAN_CACHE_ERRORS = SCAN_CACHE / "errors"
SCAN_CACHE_NOTE_ERRORS = SCAN_CACHE_ERRORS / "note_errors"
SCAN_CACHE_NOT_FOUND_ERRORS = SCAN_CACHE_ERRORS / "not_found_errors"
SCAN_CACHE_FAST_SLOW_ERRORS = SCAN_CACHE_ERRORS / "fast_slow_errors"
SCAN_CACHE_MAX_COMBO_ERRORS = SCAN_CACHE_ERRORS / "max_combo_errors"
SCAN_CACHE_LIVE_ERRORS = SCAN_CACHE_ERRORS / "live_errors"
UPLOADS_ROOT = ENV_STORAGE_ROOT / "uploads"

REMOTE_REQUEST_RETRIES = _get_int_env("REMOTE_REQUEST_RETRIES", 3)
REMOTE_REQUEST_TIMEOUT = _get_int_env("REMOTE_REQUEST_TIMEOUT", 10)
SCAN_MASTER_KEY = os.getenv("SCAN_MASTER_KEY", "").strip()
SCAN_SERVER_FOLDER_WHITELIST = [Path(item).expanduser() for item in _get_csv_env("SCAN_SERVER_FOLDER_WHITELIST")]
SCAN_MAX_FILES_PER_USER = _get_int_env("SCAN_MAX_FILES_PER_USER", 10000)
SCAN_MAX_AGE_DAYS = _get_int_env("SCAN_MAX_AGE_DAYS", 90)
SCAN_MAX_USER_STORAGE_MB = _get_int_env("SCAN_MAX_USER_STORAGE_MB", 5000)
DEV_SIMULATE_SCREENSHOT_LOCATIONS = _get_bool_env(
    "DEV_SIMULATE_SCREENSHOT_LOCATIONS",
    BANGSTATS_ENV == "dev",
)
DEV_SIMULATED_SERVER_FOLDER_ROOT = Path(
    os.getenv(
        "DEV_SIMULATED_SERVER_FOLDER_ROOT",
        str(PROJECT_ROOT / "storage" / "dev" / "simulated_server_folders"),
    ).strip()
).expanduser()
DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT = Path(
    os.getenv(
        "DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT",
        str(PROJECT_ROOT / "storage" / "dev" / "simulated_client_sources"),
    ).strip()
).expanduser()
if DEV_SIMULATE_SCREENSHOT_LOCATIONS:
    resolved_sim_root = DEV_SIMULATED_SERVER_FOLDER_ROOT.resolve()
    if not any(path.resolve() == resolved_sim_root for path in SCAN_SERVER_FOLDER_WHITELIST):
        SCAN_SERVER_FOLDER_WHITELIST.append(DEV_SIMULATED_SERVER_FOLDER_ROOT)

FAKE_SCAN_DELAY_MS = _get_int_env("FAKE_SCAN_DELAY_MS", 200)
FAKE_SCAN_ERROR_RATE = _get_int_env("FAKE_SCAN_ERROR_RATE", 15)
FAKE_SCAN_PROFILE = os.getenv("FAKE_SCAN_PROFILE", "mixed").strip().lower() or "mixed"
FAKE_SCAN_SEED = os.getenv("FAKE_SCAN_SEED", "").strip()
FAKE_TIME_SPAN_DAYS = _get_int_env("FAKE_TIME_SPAN_DAYS", 90)
FAKE_SCAN_ERROR_WEIGHTS = (
    os.getenv(
        "FAKE_SCAN_ERROR_WEIGHTS",
        "note_errors:40,not_found_errors:30,fast_slow_errors:15,max_combo_errors:10,live_errors:5",
    )
    .strip()
    .lower()
)
META_SONG_IDS = _get_csv_int_env("BANGSTATS_META_SONG_IDS")


def _merge_tree(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source_item in source_dir.iterdir():
        target_item = destination_dir / source_item.name
        if source_item.is_dir():
            _merge_tree(source_item, target_item)
            try:
                source_item.rmdir()
            except OSError:
                pass
            continue
        if not target_item.exists():
            shutil.move(str(source_item), str(target_item))
        else:
            source_item.unlink(missing_ok=True)


def migrate_legacy_cache_dirs(
    *,
    legacy_root: Path | None = None,
    env_cache_root: Path | None = None,
) -> dict[str, str]:
    resolved_legacy_root = legacy_root or (PROJECT_ROOT / "cache")
    resolved_env_cache_root = env_cache_root or (ENV_STORAGE_ROOT / "cache")
    migrations = {
        resolved_legacy_root / "remote_data_cache": resolved_env_cache_root / "remote_data_cache",
        resolved_legacy_root / "scan_data_cache": resolved_env_cache_root / "scan_data_cache",
    }

    results: dict[str, str] = {}
    for legacy_dir, destination_dir in migrations.items():
        key = legacy_dir.name
        if not legacy_dir.exists():
            results[key] = "missing"
            continue
        try:
            _merge_tree(legacy_dir, destination_dir)
            try:
                legacy_dir.rmdir()
            except OSError:
                pass
            results[key] = "migrated"
        except Exception:
            results[key] = "failed"
    return results


def migrate_legacy_storage_dirs(
    *,
    legacy_storage_root: Path | None = None,
    env_storage_root: Path | None = None,
    db_path: Path | None = None,
    db_override_set: bool | None = None,
) -> dict[str, str]:
    resolved_legacy_storage_root = legacy_storage_root or (PROJECT_ROOT / "storage")
    resolved_env_storage_root = env_storage_root or ENV_STORAGE_ROOT
    resolved_db_path = db_path or DB_PATH
    resolved_db_override_set = bool(_db_path_override) if db_override_set is None else db_override_set

    results: dict[str, str] = {}

    # Logs: merge legacy storage/logs -> storage/<env>/logs
    legacy_logs = resolved_legacy_storage_root / "logs"
    env_logs = resolved_env_storage_root / "logs"
    if legacy_logs.exists():
        try:
            _merge_tree(legacy_logs, env_logs)
            try:
                legacy_logs.rmdir()
            except OSError:
                pass
            results["logs"] = "migrated"
        except Exception:
            results["logs"] = "failed"
    else:
        results["logs"] = "missing"

    # Backups: merge legacy storage/backups -> storage/<env>/backups
    legacy_backups = resolved_legacy_storage_root / "backups"
    env_backups = resolved_env_storage_root / "backups"
    if legacy_backups.exists():
        try:
            _merge_tree(legacy_backups, env_backups)
            try:
                legacy_backups.rmdir()
            except OSError:
                pass
            results["backups"] = "migrated"
        except Exception:
            results["backups"] = "failed"
    else:
        results["backups"] = "missing"

    # DB: move legacy storage/bangstats.db -> storage/<env>/bangstats.db only when default DB path is used.
    legacy_db = resolved_legacy_storage_root / "bangstats.db"
    if resolved_db_override_set:
        results["db"] = "skipped_override"
    elif not legacy_db.exists():
        results["db"] = "missing"
    elif resolved_db_path.exists():
        results["db"] = "skipped_destination_exists"
    else:
        try:
            resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_db), str(resolved_db_path))
            results["db"] = "migrated"
        except Exception:
            results["db"] = "failed"

    return results

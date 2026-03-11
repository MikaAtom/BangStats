import random
from pathlib import Path

from loguru import logger

from bangstats_server.core.adapters.ocr.fake import generate_spread_timestamps
from bangstats_server.core.config import (
    BANGSTATS_ENV,
    DEV_SIMULATE_SCREENSHOT_LOCATIONS,
    DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT,
    DEV_SIMULATED_SERVER_FOLDER_ROOT,
)
from bangstats_server.core.services.user import UserService

_DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDATx\x9cc`\x00\x02\x00\x00\x05\x00\x01"
    b"\x0d\n\x2d\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


class DevSimulationService:
    def __init__(self):
        self.enabled = BANGSTATS_ENV == "dev" and DEV_SIMULATE_SCREENSHOT_LOCATIONS
        self.server_root = DEV_SIMULATED_SERVER_FOLDER_ROOT
        self.local_source_root = DEV_SIMULATED_CLIENT_UPLOAD_SOURCE_ROOT

    def ensure_roots(self) -> None:
        if not self.enabled:
            return
        self.server_root.mkdir(parents=True, exist_ok=True)
        self.local_source_root.mkdir(parents=True, exist_ok=True)

    def user_server_folder(self, user_id: int, *, create: bool = True) -> Path:
        folder = self.server_root / f"user_{int(user_id)}" / "server_folder"
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def user_local_source_folder(self, user_id: int, *, create: bool = True) -> Path:
        folder = self.local_source_root / f"user_{int(user_id)}" / "local_source"
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    def resolve_server_folder_path(self, user_id: int, requested_path: str) -> Path:
        default_folder = self.user_server_folder(user_id, create=True)
        raw = (requested_path or "").strip()
        if not raw or raw.lower() in {"sim", "simulated", "auto"}:
            return default_folder

        candidate = Path(raw).expanduser()
        try:
            candidate = candidate.resolve()
        except Exception:
            return default_folder

        server_root = self.server_root.resolve()
        if candidate == server_root:
            return default_folder
        if candidate == (server_root / f"user_{int(user_id)}"):
            return default_folder
        if _is_within(candidate, server_root):
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        return candidate

    def ensure_for_user(self, user_id: int, *, placeholder_count: int = 0) -> None:
        if not self.enabled:
            return
        server_folder = self.user_server_folder(user_id, create=True)
        local_folder = self.user_local_source_folder(user_id, create=True)
        if placeholder_count > 0:
            self._seed_placeholders(server_folder, count=placeholder_count)
            self._seed_placeholders(local_folder, count=placeholder_count)

    def ensure_for_existing_users(self, *, placeholder_count: int = 0) -> None:
        if not self.enabled:
            return
        self.ensure_roots()
        users = UserService().get_all_users()
        for user in users:
            try:
                self.ensure_for_user(int(user.id), placeholder_count=placeholder_count)
            except Exception as exc:
                logger.warning(f"Failed to seed simulated folders for user {getattr(user, 'id', '?')}: {exc}")

    def prepare_folder(
        self,
        folder: Path,
        *,
        count: int,
        time_span_days: int,
        clear_existing: bool,
    ) -> tuple[int, int]:
        folder.mkdir(parents=True, exist_ok=True)
        existing_before = len(self._png_files(folder))

        if clear_existing:
            for image in self._png_files(folder):
                image.unlink(missing_ok=True)

        rng = random.Random()
        timestamps = generate_spread_timestamps(max(0, int(count)), max(1, int(time_span_days)), rng)
        created = 0
        for timestamp in timestamps:
            target = folder / f"Screenshot_{int(timestamp.timestamp() * 1000)}.png"
            target.write_bytes(_DUMMY_PNG_BYTES)
            created += 1
        return existing_before, created

    def _png_files(self, folder: Path) -> list[Path]:
        return sorted(
            [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".png"]
        )

    def _seed_placeholders(self, folder: Path, *, count: int) -> None:
        existing = self._png_files(folder)
        if existing:
            return
        base_ts_ms = 1700000000000
        for idx in range(max(0, int(count))):
            target = folder / f"Screenshot_{base_ts_ms + idx}.png"
            target.write_bytes(_DUMMY_PNG_BYTES)

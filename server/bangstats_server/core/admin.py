import shutil
from datetime import datetime
from pathlib import Path


def flush_with_backup(
    targets: list[tuple[Path, str]],
    backup_base: Path,
    include_deleted_files_dir: bool = False,
) -> tuple[Path, list[str], list[str]]:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_root = backup_base / "backups" / timestamp
    if include_deleted_files_dir:
        backup_root = backup_root / "deleted files"

    moved: list[str] = []
    skipped: list[str] = []

    for source_path, fallback_name in targets:
        if not source_path.exists():
            skipped.append(str(source_path))
            continue

        backup_root.mkdir(parents=True, exist_ok=True)
        destination_name = source_path.name or fallback_name
        destination = backup_root / destination_name
        if destination.exists():
            destination = backup_root / f"{destination_name}_{datetime.now().timestamp()}"

        shutil.move(str(source_path), str(destination))
        moved.append(str(destination))

    return backup_root, moved, skipped

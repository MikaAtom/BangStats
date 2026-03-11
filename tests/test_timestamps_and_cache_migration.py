from pathlib import Path

from bangstats_server.core.config import migrate_legacy_cache_dirs, migrate_legacy_storage_dirs
from bangstats_server.core.timestamps import extract_timestamp_from_filename


def test_extract_timestamp_from_unix_ms_filename():
    assert extract_timestamp_from_filename("Screenshot_1700000000048.png") == 1700000000048


def test_extract_timestamp_keeps_existing_formats():
    value = extract_timestamp_from_filename("Screenshot_20260311_191643.png")
    assert isinstance(value, int)
    assert value > 0


def test_migrate_legacy_cache_dirs_merges_into_env_cache(tmp_path: Path):
    legacy_root = tmp_path / "cache"
    env_cache_root = tmp_path / "storage" / "dev" / "cache"

    legacy_remote = legacy_root / "remote_data_cache"
    legacy_scan = legacy_root / "scan_data_cache"
    legacy_remote.mkdir(parents=True, exist_ok=True)
    legacy_scan.mkdir(parents=True, exist_ok=True)
    (legacy_remote / "songs.json").write_text("{}", encoding="utf-8")
    (legacy_scan / "a.json").write_text("{}", encoding="utf-8")

    env_remote = env_cache_root / "remote_data_cache"
    env_remote.mkdir(parents=True, exist_ok=True)
    (env_remote / "existing.json").write_text("{}", encoding="utf-8")

    result = migrate_legacy_cache_dirs(
        legacy_root=legacy_root,
        env_cache_root=env_cache_root,
    )

    assert result["remote_data_cache"] == "migrated"
    assert result["scan_data_cache"] == "migrated"
    assert (env_remote / "songs.json").exists()
    assert (env_remote / "existing.json").exists()
    assert (env_cache_root / "scan_data_cache" / "a.json").exists()
    assert not legacy_remote.exists()
    assert not legacy_scan.exists()


def test_migrate_legacy_cache_dirs_handles_missing_sources(tmp_path: Path):
    result = migrate_legacy_cache_dirs(
        legacy_root=tmp_path / "cache",
        env_cache_root=tmp_path / "storage" / "prod" / "cache",
    )
    assert result["remote_data_cache"] == "missing"
    assert result["scan_data_cache"] == "missing"


def test_migrate_legacy_storage_dirs_moves_logs_backups_and_db(tmp_path: Path):
    legacy_storage_root = tmp_path / "storage"
    env_storage_root = tmp_path / "storage" / "dev"

    legacy_logs = legacy_storage_root / "logs"
    legacy_backups = legacy_storage_root / "backups"
    legacy_logs.mkdir(parents=True, exist_ok=True)
    legacy_backups.mkdir(parents=True, exist_ok=True)
    (legacy_logs / "app.log").write_text("log", encoding="utf-8")
    (legacy_backups / "b1.txt").write_text("backup", encoding="utf-8")
    (legacy_storage_root / "bangstats.db").write_text("db", encoding="utf-8")

    result = migrate_legacy_storage_dirs(
        legacy_storage_root=legacy_storage_root,
        env_storage_root=env_storage_root,
        db_path=env_storage_root / "bangstats.db",
        db_override_set=False,
    )

    assert result["logs"] == "migrated"
    assert result["backups"] == "migrated"
    assert result["db"] == "migrated"
    assert (env_storage_root / "logs" / "app.log").exists()
    assert (env_storage_root / "backups" / "b1.txt").exists()
    assert (env_storage_root / "bangstats.db").exists()
    assert not (legacy_storage_root / "bangstats.db").exists()


def test_migrate_legacy_storage_dirs_skips_db_when_override_set(tmp_path: Path):
    legacy_storage_root = tmp_path / "storage"
    env_storage_root = tmp_path / "storage" / "dev"
    legacy_storage_root.mkdir(parents=True, exist_ok=True)
    (legacy_storage_root / "bangstats.db").write_text("db", encoding="utf-8")

    result = migrate_legacy_storage_dirs(
        legacy_storage_root=legacy_storage_root,
        env_storage_root=env_storage_root,
        db_path=env_storage_root / "bangstats.db",
        db_override_set=True,
    )

    assert result["db"] == "skipped_override"
    assert (legacy_storage_root / "bangstats.db").exists()
    assert not (env_storage_root / "bangstats.db").exists()

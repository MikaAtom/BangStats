"""Shared pytest configuration."""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_DB_DIR = ROOT / ".pytest_tmp"
TEST_DB_PATH = TEST_DB_DIR / "bangstats.db"

TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

# Must be set before importing server app modules in tests.
os.environ["BANGSTATS_DB_PATH"] = str(TEST_DB_PATH)
os.environ["BANGSTATS_DISABLE_LEGACY_CACHE_MIGRATION"] = "1"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db():
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

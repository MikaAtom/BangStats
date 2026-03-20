from __future__ import annotations

import runpy
from pathlib import Path


def _repo_root() -> Path:
    # .../BangStats/server/bangstats_server/tools/script_entrypoints.py -> .../BangStats
    return Path(__file__).resolve().parents[3]


def _run_script(script_name: str) -> None:
    script_path = _repo_root() / "scripts" / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    runpy.run_path(str(script_path), run_name="__main__")


def heal_screenshot_filenames() -> None:
    _run_script("heal_screenshot_filenames.py")


def dedupe_screenshots() -> None:
    _run_script("dedupe_screenshots.py")


def list_screenshot_diff() -> None:
    _run_script("list_screenshot_diff.py")

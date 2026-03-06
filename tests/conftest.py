from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server"
CLIENT_PATH = ROOT / "clients" / "cli"

for path in (SERVER_PATH, CLIENT_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

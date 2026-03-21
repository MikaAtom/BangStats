#!/usr/bin/env python3
"""Start BangStats development processes with one command.

This launcher starts the API server and Web UI with a shared API target.
The CLI can be started as an optional third process.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBUI_DIR = ROOT / "clients" / "webui"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BangStats development stack.")
    parser.add_argument("--api-port", type=int, default=8010, help="API port for bangstats server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for bangstats server.")
    parser.add_argument("--with-cli", action="store_true", help="Also start the CLI client.")
    parser.add_argument(
        "--cli-extra-args",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed to bangstats client after '--'.",
    )
    return parser


def _spawn(
    name: str,
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    print(f"[dev-stack] Starting {name}: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=cwd or ROOT, env=env)


def _terminate_all(processes: list[tuple[str, subprocess.Popen[bytes]]]) -> None:
    for name, proc in processes:
        if proc.poll() is None:
            print(f"[dev-stack] Stopping {name} (pid={proc.pid})")
            proc.terminate()

    deadline = time.time() + 8
    for _, proc in processes:
        if proc.poll() is None:
            timeout = max(0, deadline - time.time())
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api_target = f"http://{args.host}:{args.api_port}"

    web_env = os.environ.copy()
    web_env["BANGSTATS_API_TARGET"] = api_target

    processes: list[tuple[str, subprocess.Popen[bytes]]] = []

    def _handle_signal(signum: int, _: object) -> None:
        print(f"\n[dev-stack] Received signal {signum}. Shutting down...")
        _terminate_all(processes)
        raise SystemExit(130)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        processes.append(
            (
                "server",
                _spawn(
                    "server",
                    [
                        "uv",
                        "run",
                        "bangstats",
                        "server",
                        "--host",
                        args.host,
                        "--port",
                        str(args.api_port),
                    ],
                ),
            )
        )

        # Give the API process a brief head start before web-ui proxying requests.
        time.sleep(1.0)

        processes.append(
            (
                "webui",
                _spawn(
                    "webui",
                    ["npm", "run", "dev"],
                    cwd=WEBUI_DIR,
                    env=web_env,
                ),
            )
        )

        if args.with_cli:
            cli_cmd = [
                "uv",
                "run",
                "bangstats",
                "client",
                "--server-url",
                api_target,
            ]
            if args.cli_extra_args:
                cli_cmd.extend(args.cli_extra_args)
            processes.append(("cli", _spawn("cli", cli_cmd)))

        print("[dev-stack] Stack started. Press Ctrl+C to stop all processes.")

        while True:
            for name, proc in processes:
                code = proc.poll()
                if code is not None:
                    print(f"[dev-stack] Process exited: {name} (code={code})")
                    _terminate_all(processes)
                    return code
            time.sleep(0.5)
    finally:
        _terminate_all(processes)


if __name__ == "__main__":
    sys.exit(main())

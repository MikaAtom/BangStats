import argparse
import importlib


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bangstats",
        description="BangStats unified launcher for server and client.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("server", help="Run BangStats API server.")
    subparsers.add_parser("client", help="Run BangStats CLI client.")
    return parser


def run(argv: list[str] | None = None) -> None:
    parsed, forwarded = build_parser().parse_known_args(argv)
    forwarded_args = list(forwarded or [])

    if parsed.command == "server":
        run_server = importlib.import_module("bangstats_server.app").run
        run_server(forwarded_args)
        return

    run_client = importlib.import_module("bangstats_cli.app").run
    run_client(forwarded_args)

from bangstats_cli.app import build_parser


def test_client_parser_defaults():
    args = build_parser().parse_args([])
    assert args.server_url == "http://localhost:8010"
    assert args.username is None
    assert args.game_id is None
    assert args.server is None
    assert args.screenshots_path is None
    assert args.skip_sync is False
    assert args.exit_after_init is False
    assert args.flush_remote_cache is False
    assert args.flush_scan_cache is False
    assert args.flush_db is False
    assert args.flush_all is False


def test_client_parser_custom_values():
    args = build_parser().parse_args(
        [
            "--server-url",
            "http://example.test:9999",
            "--username",
            "user",
            "--game-id",
            "123456",
            "--server",
            "jp",
            "--screenshots-path",
            "/tmp/screens",
            "--skip-sync",
            "--exit-after-init",
            "--flush-all",
        ]
    )
    assert args.server_url == "http://example.test:9999"
    assert args.username == "user"
    assert args.game_id == "123456"
    assert args.server == "jp"
    assert args.screenshots_path == "/tmp/screens"
    assert args.skip_sync is True
    assert args.exit_after_init is True
    assert args.flush_all is True

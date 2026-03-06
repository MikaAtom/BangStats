from bangstats.cli.app import _build_flush_targets, build_parser


def test_cli_parser_defaults():
    args = build_parser().parse_args([])

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


def test_cli_parser_accepts_dev_shortcuts():
    args = build_parser().parse_args(
        [
            "--username",
            "dev_user",
            "--game-id",
            "1234567",
            "--server",
            "en",
            "--screenshots-path",
            "/tmp/screens",
            "--skip-sync",
            "--exit-after-init",
        ]
    )

    assert args.username == "dev_user"
    assert args.game_id == "1234567"
    assert args.server == "en"
    assert args.screenshots_path == "/tmp/screens"
    assert args.skip_sync is True
    assert args.exit_after_init is True


def test_cli_parser_flush_all_enables_all_targets():
    args = build_parser().parse_args(["--flush-all"])
    targets = _build_flush_targets(args)
    target_names = {path.name for path, _ in targets}

    assert "remote_data_cache" in target_names
    assert "scan_data_cache" in target_names
    assert "bangstats.db" in target_names


def test_cli_parser_flush_specific_targets():
    args = build_parser().parse_args(["--flush-scan-cache", "--flush-db"])
    targets = _build_flush_targets(args)
    target_names = {path.name for path, _ in targets}

    assert target_names == {"scan_data_cache", "bangstats.db"}

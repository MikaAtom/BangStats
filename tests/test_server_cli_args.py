from bangstats_server.app import _build_flush_targets, build_parser


def test_server_parser_defaults():
    args = build_parser().parse_args([])

    assert args.host == "0.0.0.0"
    assert args.port == 8010
    assert args.reload is False
    assert args.flush_remote_cache is False
    assert args.flush_scan_cache is False
    assert args.flush_db is False
    assert args.flush_all is False


def test_server_parser_accepts_runtime_overrides():
    args = build_parser().parse_args(["--host", "127.0.0.1", "--port", "9000", "--reload"])

    assert args.host == "127.0.0.1"
    assert args.port == 9000
    assert args.reload is True


def test_server_flush_all_enables_all_targets():
    args = build_parser().parse_args(["--flush-all"])
    targets = _build_flush_targets(args)
    target_names = {path.name for path, _ in targets}

    assert "remote_data_cache" in target_names
    assert "scan_data_cache" in target_names
    assert "bangstats.db" in target_names


def test_server_flush_specific_targets():
    args = build_parser().parse_args(["--flush-scan-cache", "--flush-db"])
    targets = _build_flush_targets(args)
    target_names = {path.name for path, _ in targets}

    assert target_names == {"scan_data_cache", "bangstats.db"}

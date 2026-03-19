from datetime import datetime, timezone
from types import SimpleNamespace

from bangstats_server.core.services.event_time import event_is_active, get_event_window_ms, parse_event_timestamp_ms


def test_parse_event_timestamp_ms_supports_string_and_int_values():
    assert parse_event_timestamp_ms({"en": "1773450000000"}, language="en") == 1773450000000
    assert parse_event_timestamp_ms({"en": 1773989999000}, language="en") == 1773989999000
    assert parse_event_timestamp_ms(1773450000000, language="en") == 1773450000000


def test_event_window_and_active_match_event_295_style_values():
    event = SimpleNamespace(
        event_start_at={"en": "1773450000000"},
        event_end_at={"en": "1773989999000"},
    )
    start, end = get_event_window_ms(event, language="en")
    assert start == 1773450000000
    assert end == 1773989999000

    ts = int(datetime(2026, 3, 19, 18, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert event_is_active(event, timestamp_ms=ts, language="en") is True


def test_event_is_inactive_when_server_window_missing():
    event = SimpleNamespace(
        event_start_at={"en": "1773450000000", "kr": None},
        event_end_at={"en": "1773989999000", "kr": None},
    )
    ts = int(datetime(2026, 3, 19, 18, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert event_is_active(event, timestamp_ms=ts, language="kr") is False

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from bangstats_server.core.adapters.ocr import fake as fake_module
from bangstats_server.core.adapters.ocr.fake import FakeScannerService


def _song() -> SimpleNamespace:
    return SimpleNamespace(
        internal_song_id=125,
        name={"en": "Unite! From A To Z", "jp": "Unite!"},
        levels={"easy": [8], "normal": [14], "hard": [20], "expert": [26], "special": [29]},
        note_counts={"easy": [120], "normal": [260], "hard": [450], "expert": [700], "special": [850]},
    )


@pytest.fixture
def fake_services(monkeypatch: pytest.MonkeyPatch):
    class _SongService:
        def get_all_songs(self):
            return [_song()]

    class _EventService:
        def search_events_by_date(self, _timestamp):
            return None

    monkeypatch.setattr(fake_module, "SongService", _SongService)
    monkeypatch.setattr(fake_module, "EventService", _EventService)


def test_fake_scanner_returns_expected_shape(fake_services, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fake_module, "FAKE_SCAN_PROFILE", "mixed")
    monkeypatch.setattr(fake_module, "FAKE_SCAN_ERROR_RATE", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_DELAY_MS", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_SEED", "42")
    scanner = FakeScannerService()
    payload = scanner.generate_response("fake", "fake", "Screenshot_1710000000000.png")
    required = {
        "score",
        "high_score",
        "is_new_record",
        "score_rank",
        "live_type",
        "perfect",
        "great",
        "good",
        "bad",
        "miss",
        "fast",
        "slow",
        "max_combo",
        "difficulty",
        "song_name_from_top_bar_text",
    }
    assert required.issubset(payload.keys())


def test_fake_scanner_profile_affects_output(fake_services, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fake_module, "FAKE_SCAN_DELAY_MS", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_ERROR_RATE", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_SEED", "7")

    monkeypatch.setattr(fake_module, "FAKE_SCAN_PROFILE", "beginner")
    beginner = FakeScannerService().generate_response("fake", "fake", "Screenshot_1710000000001.png")
    monkeypatch.setattr(fake_module, "FAKE_SCAN_PROFILE", "expert")
    expert = FakeScannerService().generate_response("fake", "fake", "Screenshot_1710000000002.png")

    assert beginner["miss"] >= expert["miss"]
    assert beginner["perfect"] <= expert["perfect"]


def test_fake_scanner_deterministic_seed(fake_services, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fake_module, "FAKE_SCAN_DELAY_MS", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_ERROR_RATE", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_PROFILE", "mixed")
    monkeypatch.setattr(fake_module, "FAKE_SCAN_SEED", "99")
    first = FakeScannerService().generate_response("fake", "fake", "Screenshot_1710000000003.png")
    second = FakeScannerService().generate_response("fake", "fake", "Screenshot_1710000000003.png")
    assert first == second


def test_fake_scanner_error_rate_and_weights(fake_services, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fake_module, "FAKE_SCAN_DELAY_MS", 0)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_PROFILE", "mixed")
    monkeypatch.setattr(fake_module, "FAKE_SCAN_SEED", "123")
    monkeypatch.setattr(fake_module, "FAKE_SCAN_ERROR_RATE", 100)
    monkeypatch.setattr(fake_module, "FAKE_SCAN_ERROR_WEIGHTS", "not_found_errors:100")
    payload = FakeScannerService().generate_response("fake", "fake", "Screenshot_1710000000004.png")
    assert str(payload["song_name_from_top_bar_text"]).startswith("fake_missing_")


def test_generate_spread_timestamps_returns_sorted_values_in_range():
    now = datetime.now()
    span_days = 30
    values = fake_module.generate_spread_timestamps(
        count=50,
        span_days=span_days,
        rng=fake_module.random.Random(1),
    )

    assert len(values) == 50
    assert values == sorted(values)
    lower_bound = now - timedelta(days=span_days, seconds=1)
    upper_bound = datetime.now() + timedelta(seconds=1)
    for value in values:
        assert lower_bound <= value <= upper_bound

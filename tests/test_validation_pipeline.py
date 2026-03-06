from pathlib import Path
from types import SimpleNamespace
import json

from bangstats_server.core.services.scan import ScanService
from bangstats_server.core.services.validation import ValidationResult, ValidationService


class _FakeSongService:
    def __init__(self, songs_by_id=None, songs_by_note_count=None):
        self.songs_by_id = songs_by_id or {}
        self.songs_by_note_count = songs_by_note_count or {}

    def get_song_by_internal_id(self, song_id):
        return self.songs_by_id.get(song_id)

    def get_songs_by_difficulty(self, difficulty, total_notes):
        return []

    def get_songs_by_note_count(self, note_count, difficulty=None):
        key = (note_count, difficulty)
        if key in self.songs_by_note_count:
            return self.songs_by_note_count[key]
        if (note_count, None) in self.songs_by_note_count:
            return self.songs_by_note_count[(note_count, None)]
        return []


class _FakeEventService:
    def __init__(self, event=None):
        self.event = event

    def search_events_by_date(self, timestamp):
        return self.event


def _build_validation_service(song_service, event_service, stripped_songs=None):
    service = ValidationService.__new__(ValidationService)
    service.event_type_to_live_types = {
        "festival": ["free live", "multi live", "team live battle"],
        "challenge": ["free live", "multi live", "challenge live"],
    }
    service.fuzzy_threshold = 0.8
    service.song_service = song_service
    service.event_service = event_service
    service.stripped_songs = stripped_songs or {}
    service.name_fixes = {}
    return service


def test_validation_returns_live_error_for_forbidden_live_type():
    song = SimpleNamespace(internal_song_id=10, note_counts={"expert": 100})
    service = _build_validation_service(
        song_service=_FakeSongService({10: song}),
        event_service=_FakeEventService(SimpleNamespace(event_type="festival")),
        stripped_songs={"testsong": 10},
    )

    result = service.validate(
        "Screenshot_20260306_140402.png",
        {
            "song_name_from_top_bar_text": "Test Song",
            "difficulty": "expert",
            "perfect": 100,
            "great": 0,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "max_combo": 100,
            "fast": 0,
            "slow": 0,
            "live_type": "challenge live",
        },
    )

    assert result.is_valid is False
    assert result.error_type == "live_errors"
    assert result.severity == "error"
    assert result.confidence == 1.0


def test_validation_applies_romeo_note_exception():
    song = SimpleNamespace(internal_song_id=11, note_counts={"hard": 500})
    service = _build_validation_service(
        song_service=_FakeSongService({11: song}),
        event_service=_FakeEventService(None),
        stripped_songs={"romeo": 11},
    )

    result = service.validate(
        "Screenshot_20260306_140402.png",
        {
            "song_name_from_top_bar_text": "Romeo",
            "difficulty": "hard",
            "perfect": 474,
            "great": 0,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "max_combo": 474,
            "fast": 0,
            "slow": 0,
            "live_type": "free live",
        },
    )

    assert result.is_valid is True
    assert result.error_type is None
    assert result.severity == "warning"
    assert result.confidence == 1.0


def test_validation_resolves_silvous_variant_song_id():
    song_462 = SimpleNamespace(internal_song_id=462, note_counts={"expert": 695})
    service = _build_validation_service(
        song_service=_FakeSongService({462: song_462}),
        event_service=_FakeEventService(None),
        stripped_songs={},
    )

    result = service.validate(
        "Screenshot_20260306_140402.png",
        {
            "song_name_from_top_bar_text": "Sil vous President",
            "difficulty": "expert",
            "perfect": 695,
            "great": 0,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "max_combo": 695,
            "fast": 0,
            "slow": 0,
            "live_type": "free live",
        },
    )

    assert result.is_valid is True
    assert result.resolved_song_id == 462
    assert result.confidence == 0.95
    assert result.severity == "info"


def test_validation_success_sets_info_severity_and_exact_confidence():
    song = SimpleNamespace(internal_song_id=21, note_counts={"expert": 100})
    service = _build_validation_service(
        song_service=_FakeSongService({21: song}),
        event_service=_FakeEventService(None),
        stripped_songs={"testsong": 21},
    )

    result = service.validate(
        "Screenshot_20260306_140402.png",
        {
            "song_name_from_top_bar_text": "Test Song",
            "difficulty": "expert",
            "perfect": 100,
            "great": 0,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "max_combo": 100,
            "fast": 0,
            "slow": 0,
            "live_type": "free live",
        },
    )

    assert result.is_valid is True
    assert result.severity == "info"
    assert result.confidence == 1.0


def test_validation_resolves_fuzzy_name_from_note_count_candidates():
    song = SimpleNamespace(
        internal_song_id=125,
        name={"en": "Unite! From A To Z"},
        note_counts={"expert": 713},
    )
    service = _build_validation_service(
        song_service=_FakeSongService(
            songs_by_id={125: song},
            songs_by_note_count={(713, "expert"): [song]},
        ),
        event_service=_FakeEventService(None),
        stripped_songs={},
    )

    result = service.validate(
        "Screenshot_20260306_140402.png",
        {
            "song_name_from_top_bar_text": "Unitel From A To Z",
            "difficulty": "expert",
            "perfect": 700,
            "great": 13,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "max_combo": 713,
            "fast": 0,
            "slow": 13,
            "live_type": "free live",
        },
    )

    assert result.is_valid is True
    assert result.resolved_song_id == 125
    assert result.error_type is None
    assert result.severity == "warning"
    assert result.confidence >= 0.8


def test_load_name_fixes_from_json_file(tmp_path: Path):
    fixes_path = tmp_path / "name_fixes.json"
    fixes_path.write_text(
        json.dumps({"foo": "bar", "judgelight": "level5judgelight"}),
        encoding="utf-8",
    )

    service = ValidationService.__new__(ValidationService)
    loaded = service._load_name_fixes(fixes_path)

    assert loaded == {"foo": "bar", "judgelight": "level5judgelight"}

    service.name_fixes = loaded
    assert service._known_name_sanitize("foojudgelight") == "barlevel5judgelight"


def test_scan_summary_counts_persisted_records(tmp_path: Path):
    image_name = "Screenshot_20260306_140402.png"
    (tmp_path / image_name).write_text("fake image")

    scan_service = ScanService.__new__(ScanService)
    scan_service.default_model = "test-model"
    scan_service.validation_service = SimpleNamespace(
        validate=lambda *_: ValidationResult(
            is_valid=True,
            error_type=None,
            resolved_song_id=123,
            normalized={},
            reasons=[],
        )
    )
    persisted_payloads = []
    def _create_and_capture(payload):
        persisted_payloads.append(payload)
        return SimpleNamespace(id=1)

    scan_service.screenshot_service = SimpleNamespace(create_screenshot=_create_and_capture)
    scan_service._scan_single_image = lambda *_: (
        {
            "score": 1000,
            "high_score": 1000,
            "is_new_record": True,
            "score_rank": "S",
            "live_type": "free live",
            "perfect": 100,
            "great": 0,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "fast": 0,
            "slow": 0,
            "max_combo": 100,
            "difficulty": "expert",
            "song_name_from_top_bar_text": "Test Song",
        },
        None,
    )
    scan_service._store_result = lambda *args, **kwargs: None
    scan_service._extract_timestamp_from_filename = lambda *_: 1700000000000

    result = scan_service.scan_images(
        str(tmp_path),
        [image_name],
        user_id=1,
        persist_to_db=True,
    )

    assert result["total_scanned"] == 1
    assert result["successful"] == 1
    assert result["validated"] == 1
    assert result["persisted"] == 1
    assert result["failed_to_persist"] == 0
    assert len(persisted_payloads) == 1


def test_scan_writes_validation_artifact(tmp_path: Path):
    image_name = "Screenshot_20260306_140402.png"
    image_path = tmp_path / image_name
    image_path.write_text("fake image")

    scan_service = ScanService.__new__(ScanService)
    scan_service.default_model = "test-model"
    scan_service.cache_successful = tmp_path / "successful"
    scan_service.cache_errors = tmp_path / "errors"
    scan_service.cache_error_note = scan_service.cache_errors / "note_errors"
    scan_service.cache_error_not_found = scan_service.cache_errors / "not_found_errors"
    scan_service.cache_error_fast_slow = scan_service.cache_errors / "fast_slow_errors"
    scan_service.cache_error_max_combo = scan_service.cache_errors / "max_combo_errors"
    scan_service.cache_error_live = scan_service.cache_errors / "live_errors"
    for folder in [
        scan_service.cache_successful,
        scan_service.cache_errors,
        scan_service.cache_error_note,
        scan_service.cache_error_not_found,
        scan_service.cache_error_fast_slow,
        scan_service.cache_error_max_combo,
        scan_service.cache_error_live,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    validation_result = ValidationResult(
        is_valid=True,
        error_type=None,
        resolved_song_id=123,
        normalized={"song_name": "testsong", "difficulty": "expert", "total_notes": 100},
        reasons=["resolved_exact_name"],
        severity="info",
        confidence=1.0,
    )
    scan_service.validation_service = SimpleNamespace(validate=lambda *_: validation_result)
    scan_service.screenshot_service = SimpleNamespace(create_screenshot=lambda payload: None)
    scan_service._scan_single_image = lambda *_: (
        {
            "score": 1000,
            "high_score": 1000,
            "is_new_record": True,
            "score_rank": "S",
            "live_type": "free live",
            "perfect": 100,
            "great": 0,
            "good": 0,
            "bad": 0,
            "miss": 0,
            "fast": 0,
            "slow": 0,
            "max_combo": 100,
            "difficulty": "expert",
            "song_name_from_top_bar_text": "Test Song",
        },
        None,
    )

    scan_service.scan_images(str(tmp_path), [image_name], persist_to_db=False)

    artifact_path = scan_service.cache_successful / "Screenshot_20260306_140402.validation.json"
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["severity"] == "info"
    assert artifact["confidence"] == 1.0
    assert artifact["resolved_song_id"] == 123


def test_import_json_folder_canonicalizes_filename_and_persists(tmp_path: Path):
    json_name = "Screenshot_20260306_140402_BanG Dream!.json"
    (tmp_path / json_name).write_text(
        json.dumps(
            {
                "score": 1000,
                "high_score": 1000,
                "is_new_record": True,
                "score_rank": "S",
                "live_type": "free live",
                "free_live_data": -1,
                "team_live_data": -1,
                "perfect": 100,
                "great": 0,
                "good": 0,
                "bad": 0,
                "miss": 0,
                "fast": 0,
                "slow": 0,
                "max_combo": 100,
                "difficulty": "expert",
                "song_name_from_top_bar_text": "Test Song",
            }
        ),
        encoding="utf-8",
    )

    scan_service = ScanService.__new__(ScanService)
    scan_service.cache_successful = tmp_path / "successful"
    scan_service.cache_errors = tmp_path / "errors"
    scan_service.cache_error_note = scan_service.cache_errors / "note_errors"
    scan_service.cache_error_not_found = scan_service.cache_errors / "not_found_errors"
    scan_service.cache_error_fast_slow = scan_service.cache_errors / "fast_slow_errors"
    scan_service.cache_error_max_combo = scan_service.cache_errors / "max_combo_errors"
    scan_service.cache_error_live = scan_service.cache_errors / "live_errors"
    for folder in [
        scan_service.cache_successful,
        scan_service.cache_errors,
        scan_service.cache_error_note,
        scan_service.cache_error_not_found,
        scan_service.cache_error_fast_slow,
        scan_service.cache_error_max_combo,
        scan_service.cache_error_live,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    scan_service.validation_service = SimpleNamespace(
        validate=lambda *_: ValidationResult(
            is_valid=True,
            error_type=None,
            resolved_song_id=123,
            normalized={},
            reasons=[],
        )
    )
    persisted_payloads = []
    scan_service.screenshot_service = SimpleNamespace(
        create_screenshot=lambda payload: persisted_payloads.append(payload) or SimpleNamespace(id=1)
    )
    scan_service._extract_timestamp_from_filename = lambda *_: 1700000000000

    result = scan_service.import_json_folder(
        folder_path=str(tmp_path),
        user_id=1,
        persist_to_db=True,
    )

    assert result["total_scanned"] == 1
    assert result["persisted"] == 1
    assert len(persisted_payloads) == 1
    assert persisted_payloads[0]["filename"] == "Screenshot_20260306_140402_BanG Dream!.png"
    assert (
        scan_service.cache_successful
        / "Screenshot_20260306_140402_BanG Dream!.validation.json"
    ).exists()


def test_split_image_list_balances_chunks():
    scan_service = ScanService.__new__(ScanService)
    chunks = scan_service._split_image_list(
        [f"Screenshot_{idx}.png" for idx in range(1, 11)],
        4,
    )
    assert [len(c) for c in chunks] == [3, 3, 2, 2]
    assert chunks[0][0] == "Screenshot_1.png"
    assert chunks[-1][-1] == "Screenshot_10.png"


def test_parallel_scan_aggregates_worker_results(monkeypatch, tmp_path: Path):
    for name in ["Screenshot_1.png", "Screenshot_2.png", "Screenshot_3.png", "Screenshot_4.png"]:
        (tmp_path / name).write_text("fake image")

    scan_service = ScanService.__new__(ScanService)
    scan_service.ocr_provider = "gemini"
    scan_service.default_model = "test-model"
    scan_service._init_results = ScanService._init_results.__get__(scan_service, ScanService)
    scan_service._split_image_list = ScanService._split_image_list.__get__(scan_service, ScanService)
    scan_service._merge_scan_results = ScanService._merge_scan_results.__get__(scan_service, ScanService)
    scan_service._validate_parallel_mode = lambda **_: ["k1", "k2", "k3", "k4"]

    def _fake_worker(**kwargs):
        chunk = kwargs["image_list"]
        return {
            "total_scanned": len(chunk),
            "successful": len(chunk),
            "errors": {},
            "error_files": {},
            "validated": len(chunk),
            "persisted": len(chunk),
            "failed_to_persist": 0,
            "skipped_duplicates": 0,
            "error_rate": 0.0,
        }

    scan_service._scan_images_worker = _fake_worker

    result = ScanService.scan_images(
        scan_service,
        images_folder=str(tmp_path),
        image_list=["Screenshot_1.png", "Screenshot_2.png", "Screenshot_3.png", "Screenshot_4.png"],
        user_id=1,
        persist_to_db=True,
        parallel_workers=2,
        keys_per_worker=2,
    )

    assert result["total_scanned"] == 4
    assert result["successful"] == 4
    assert result["persisted"] == 4
    assert result["additional"]["parallel_enabled"] is True
    assert result["additional"]["mode"] == "2x2"

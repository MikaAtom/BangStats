import sys
import types

from bangstats_server.core.adapters.ocr import get_ocr_service
from bangstats_server.core.db.repositories.screenshot_repo import ScreenshotRepository


def test_duplicate_prevention_short_circuits_create():
    repo = ScreenshotRepository.__new__(ScreenshotRepository)
    repo.get_by_user_and_filename = lambda *_: object()

    created, err = repo.create({"user_id": 1, "filename": "Screenshot_1.png"})
    assert created is None
    assert err == "duplicate"


def test_duplicate_prevention_works_for_canonical_png_filename():
    repo = ScreenshotRepository.__new__(ScreenshotRepository)
    repo.get_by_user_and_filename = lambda *_: object()

    created, err = repo.create(
        {"user_id": 1, "filename": "Screenshot_20260306_140402_BanG Dream!.png"}
    )
    assert created is None
    assert err == "duplicate"


def test_ocr_factory_gemini(monkeypatch):
    fake_module = types.ModuleType("bangstats_server.core.adapters.ocr.gemini")

    class FakeGeminiModelService:
        pass

    fake_module.GoogleModelService = FakeGeminiModelService
    monkeypatch.setitem(sys.modules, "bangstats_server.core.adapters.ocr.gemini", fake_module)

    service = get_ocr_service("gemini")
    assert isinstance(service, FakeGeminiModelService)


def test_ocr_factory_ollama(monkeypatch):
    fake_module = types.ModuleType("bangstats_server.core.adapters.ocr.ollama")

    class FakeOllamaModelService:
        pass

    fake_module.OllamaModelService = FakeOllamaModelService
    monkeypatch.setitem(sys.modules, "bangstats_server.core.adapters.ocr.ollama", fake_module)

    service = get_ocr_service("ollama")
    assert isinstance(service, FakeOllamaModelService)

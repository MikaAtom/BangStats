import sys
import types

from bangstats.adapters.ocr import get_ocr_service
from bangstats.database.repositories.screenshot_repo import ScreenshotRepository


def test_duplicate_prevention_short_circuits_create():
    repo = ScreenshotRepository.__new__(ScreenshotRepository)
    repo.get_by_user_and_filename = lambda *_: object()

    created, err = repo.create({"user_id": 1, "filename": "Screenshot_1.png"})
    assert created is None
    assert err == "duplicate"


def test_ocr_factory_gemini(monkeypatch):
    fake_module = types.ModuleType("bangstats.adapters.ocr.gemini")

    class FakeGeminiModelService:
        pass

    fake_module.GoogleModelService = FakeGeminiModelService
    monkeypatch.setitem(sys.modules, "bangstats.adapters.ocr.gemini", fake_module)

    service = get_ocr_service("gemini")
    assert isinstance(service, FakeGeminiModelService)


def test_ocr_factory_ollama(monkeypatch):
    fake_module = types.ModuleType("bangstats.adapters.ocr.ollama")

    class FakeOllamaModelService:
        pass

    fake_module.OllamaModelService = FakeOllamaModelService
    monkeypatch.setitem(sys.modules, "bangstats.adapters.ocr.ollama", fake_module)

    service = get_ocr_service("ollama")
    assert isinstance(service, FakeOllamaModelService)

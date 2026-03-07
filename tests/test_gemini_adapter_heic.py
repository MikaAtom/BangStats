from __future__ import annotations

import types
import sys

from bangstats_server.core.adapters.ocr.gemini import GoogleModelService
from bangstats_server.core.adapters.ocr import gemini as gemini_module


def test_prepare_image_payload_converts_heic_to_png(monkeypatch, tmp_path):
    source = tmp_path / "BanG Dream_2026-02-18-17-32-18.heic"
    source.write_bytes(b"heic-bytes")

    class _FakeConvertedImage:
        def save(self, output, format):  # noqa: A002
            assert format == "PNG"
            output.write(b"png-bytes")

    class _FakeOpenedImage:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def convert(self, mode):
            assert mode == "RGB"
            return _FakeConvertedImage()

    def _fake_open(path):
        assert str(path).endswith(".heic")
        return _FakeOpenedImage()

    fake_pillow_heif = types.ModuleType("pillow_heif")
    fake_pillow_heif.register_heif_opener = lambda: None

    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = types.SimpleNamespace(open=_fake_open)

    monkeypatch.setitem(sys.modules, "pillow_heif", fake_pillow_heif)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)

    service = GoogleModelService.__new__(GoogleModelService)
    image_bytes, mime_type = service._prepare_image_payload(str(source))

    assert mime_type == "image/png"
    assert image_bytes == b"png-bytes"


def test_generate_response_uses_jpeg_mime_type(monkeypatch, tmp_path):
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"jpg-bytes")
    captured = {}

    class _FakePart:
        @staticmethod
        def from_text(text):
            return {"text": text}

        @staticmethod
        def from_bytes(*, data, mime_type):
            captured["data"] = data
            captured["mime_type"] = mime_type
            return {"bytes": True}

    class _FakeContent:
        def __init__(self, role, parts):
            self.role = role
            self.parts = parts

    class _FakeConfig:
        def __init__(self, temperature):
            self.temperature = temperature

    class _FakeModels:
        def generate_content(self, *, model, contents, config):
            assert model == "fake-model"
            assert contents and config
            return types.SimpleNamespace(text='{"ok": true}')

    fake_genai = types.SimpleNamespace(
        types=types.SimpleNamespace(
            Part=_FakePart,
            Content=_FakeContent,
            GenerateContentConfig=_FakeConfig,
        )
    )
    monkeypatch.setattr(gemini_module, "genai", fake_genai)

    service = GoogleModelService.__new__(GoogleModelService)
    service.clients = [types.SimpleNamespace(models=_FakeModels())]
    service.client = service.clients[0]

    payload = service.generate_response("fake-model", "prompt", str(image_path))

    assert payload["ok"] is True
    assert captured["mime_type"] == "image/jpeg"
    assert captured["data"] == b"jpg-bytes"

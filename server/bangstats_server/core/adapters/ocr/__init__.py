"""OCR adapters and OCR-specific assets."""

from bangstats_server.core.config import OCR_PROVIDER


def get_ocr_service(provider: str | None = None):
    resolved = (provider or OCR_PROVIDER or "gemini").strip().lower()
    if resolved == "fake":
        from bangstats_server.core.adapters.ocr.fake import FakeScannerService

        return FakeScannerService()
    if resolved == "ollama":
        from bangstats_server.core.adapters.ocr.ollama import OllamaModelService

        return OllamaModelService()

    from bangstats_server.core.adapters.ocr.gemini import GoogleModelService

    return GoogleModelService()

"""OCR adapters and OCR-specific assets."""

from bangstats.config import OCR_PROVIDER


def get_ocr_service(provider: str | None = None):
    resolved = (provider or OCR_PROVIDER or "gemini").strip().lower()
    if resolved == "ollama":
        from bangstats.adapters.ocr.ollama import OllamaModelService

        return OllamaModelService()

    from bangstats.adapters.ocr.gemini import GoogleModelService

    return GoogleModelService()

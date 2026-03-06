import ollama
import json

from bangstats_server.core.config import OLLAMA_MODEL, OLLAMA_URL


class OllamaModelService:
    def __init__(self):
        self.default_model = OLLAMA_MODEL
        self.url = OLLAMA_URL
        self.client = ollama.Client(host=self.url)

    def get_available_models(self) -> list[str]:
        """Fetch the list of available models from Ollama."""
        models = self.client.list()
        return [model.model for model in models.models]

    def generate_response(self, model: str, prompt: str, image_path: str) -> dict:
        """Generate OCR response via Ollama."""
        selected_model = (model or self.default_model).strip() or self.default_model
        options = {
            "temperature": 0.5,
            "top_p": 0.5,
        }

        messages = [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "images": [image_path],
            },
        ]

        try:
            response = self.client.chat(model=selected_model, messages=messages, options=options)
        except Exception as exc:
            raise RuntimeError(f"Ollama request failed ({self.url}): {exc}") from exc

        response_text = response["message"]["content"]
        if not response_text.startswith("{") or not response_text.endswith("}"):
            response_lines = response_text.splitlines()
            if len(response_lines) > 2:
                response_text = "\n".join(response_lines[1:-1])
            else:
                return {}

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {}


def get_available_models() -> list[str]:
    return OllamaModelService().get_available_models()


def generate_response(model: str, prompt: str, image_path: str) -> dict:
    return OllamaModelService().generate_response(model, prompt, image_path)

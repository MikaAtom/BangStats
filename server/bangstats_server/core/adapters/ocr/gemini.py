from google import genai
from io import BytesIO
import json
from pathlib import Path
from typing import Optional

from bangstats_server.core.config import GOOGLE_API_KEY


class GoogleModelService:
    def __init__(self, api_keys: Optional[list[str]] = None):
        if api_keys is not None:
            self.API_KEYS = [k.strip() for k in api_keys if k and k.strip()]
        else:
            raw = GOOGLE_API_KEY
            self.API_KEYS = [k.strip() for k in raw.split(",") if k.strip()]
        if not self.API_KEYS:
            raise ValueError(
                "GOOGLE_API_KEY is not set. Set it in the environment or in a .env file."
            )
        self.clients = [genai.Client(api_key=key) for key in self.API_KEYS]
        self.client = self.clients[0]

    def switch_client(self):
        """
        Switches to the next available client in the list of API keys.
        This is useful for handling rate limits or quota issues.
        """
        current_index = self.clients.index(self.client)
        next_index = (current_index + 1) % len(self.clients)
        self.client = self.clients[next_index]

    def get_available_models(self) -> list:
        """
        Fetches the list of available models from the Google GenAI service.

        Returns:
            list: A list of model names that support generateContent.
        """
        models = self.client.models.list()
        return [
            model.name.replace("models/", "")
            for model in models
            if "generateContent" in model.supported_actions
        ]

    def _resolve_mime_type(self, image_path: str) -> str:
        suffix = Path(image_path).suffix.lower()
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".heic": "image/heic",
            ".heif": "image/heif",
        }
        return mapping.get(suffix, "application/octet-stream")

    def _convert_heic_to_png_bytes(self, image_path: str) -> bytes:
        try:
            import pillow_heif
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "HEIC/HEIF support requires Pillow and pillow-heif. Install dependencies and retry."
            ) from exc

        try:
            pillow_heif.register_heif_opener()
            with Image.open(image_path) as image:
                converted = image.convert("RGB")
                with BytesIO() as output:
                    converted.save(output, format="PNG")
                    return output.getvalue()
        except Exception as exc:
            raise RuntimeError(f"Failed to convert HEIC/HEIF image: {exc}") from exc

    def _prepare_image_payload(self, image_path: str) -> tuple[bytes, str]:
        mime_type = self._resolve_mime_type(image_path)
        if mime_type in {"image/heic", "image/heif"}:
            return self._convert_heic_to_png_bytes(image_path), "image/png"

        with open(image_path, "rb") as image_file:
            return image_file.read(), mime_type

    def generate_response(self, model: str, prompt: str, image_path: str) -> dict:
        """
        Generates a response using the specified model, prompt, and image.

        Args:
            model (str): The name of the model to use.
            prompt (str): The text prompt to send to the model.
            image_path (str): The path to the image file to include in the request.

        Returns:
            dict: The JSON response from the model.
        """
        image_bytes, mime_type = self._prepare_image_payload(image_path)

        config = genai.types.GenerateContentConfig(temperature=0.7)

        contents = [
            genai.types.Content(
                role="user",
                parts=[
                    genai.types.Part.from_text(text=prompt),
                    genai.types.Part.from_bytes(
                        data=image_bytes, mime_type=mime_type
                    ),
                ],
            ),
        ]
        response = None
        max_attempts = max(1, len(self.clients) * 3)
        for _ in range(max_attempts):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as error_message:
                err_text = str(error_message)
                if "429" in err_text or "quota" in err_text.lower() or "rate limit" in err_text.lower():
                    self.switch_client()
                    continue
                raise RuntimeError(f"Gemini request failed: {error_message}") from error_message

        if response is None:
            raise RuntimeError(
                "Gemini request failed after retries due to quota/rate-limit limits."
            )

        # if first line is not "{" or last line is not "}", remove first and last lines
        if not response.text.startswith("{") or not response.text.endswith("}"):
            # Remove first and last lines
            response_text = response.text.splitlines()
            if len(response_text) > 2:
                response_text = "\n".join(response_text[1:-1])
            else:
                return {}
        else:
            response_text = response.text

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {}

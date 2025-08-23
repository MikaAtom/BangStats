from google import genai
import json
import os


class GoogleModelService:
    API_KEYS = os.getenv("GOOGLE_API_KEY").split(",")

    def __init__(self):
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
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        config = genai.types.GenerateContentConfig(temperature=0.7)

        contents = [
            genai.types.Content(
                role="user",
                parts=[
                    genai.types.Part.from_text(text=prompt),
                    genai.types.Part.from_bytes(
                        data=image_bytes, mime_type="image/png"
                    ),
                ],
            ),
        ]
        response = None
        while response is None:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
            #
            except Exception as error_message:
                if (
                    "429" in error_message
                    or "quota" in error_message.lower()
                    or "rate limit" in error_message.lower()
                ):
                    response = None
                    self.switch_client()
                    continue

        # if first line is not "{" or last line is not "}", remove first and last lines
        if not response.text.startswith("{") or not response.text.endswith("}"):
            # Remove first and last lines
            response_text = response.text.splitlines()
            if len(response_text) > 2:
                response_text = "\n".join(response_text[1:-1])
            else:
                print("Response is not valid JSON.")
                return {}
        else:
            response_text = response.text

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return {}

import ollama
import json


def get_available_models() -> list:
    """
    Fetches the list of available models from the Ollama service.

    Returns:
        list: A list of model names.
    """
    models = ollama.list()
    return [model.model for model in models.models]


def generate_response(model: str, prompt: str, image_path: str) -> dict:
    """
    Generates a response using the specified model, prompt, and image.

    Args:
        model (str): The name of the model to use.
        prompt (str): The text prompt to send to the model.
        image_path (str): The path to the image file to include in the request.

    Returns:
        dict: The JSON response from the model.
    """

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
        }
    ]

    response = ollama.chat(model=model, messages=messages, options=options)
    response_text = response["message"]["content"]

    # if first line is not "{" or last line is not "}", remove first and last lines
    if not response_text.startswith("{") or not response_text.endswith("}"):
        # Remove first and last lines
        response_text = response_text.splitlines()
        if len(response_text) > 2:
            response_text = "\n".join(response_text[1:-1])
        else:
            print("Response is not valid JSON.")
            return {}

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return {}

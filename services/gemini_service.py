import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_api_key = os.getenv("GEMINI_API_KEY")
_models_cache = {}

# Default model settings
active_settings = {
    "model_name": "gemini-2.5-flash",
    "temperature": 0.7,
    "max_tokens": 2048
}

class GeminiError(Exception):
    """Raised when Gemini API calls fail or are misconfigured."""

def _get_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if not key or key.strip() == "":
        raise GeminiError("GEMINI_API_KEY is missing. Please set it in your .env file.")
    return key.strip()

def set_active_settings(model_name: str, temperature: float, max_tokens: int):
    """Updates the global active model settings."""
    active_settings["model_name"] = model_name
    active_settings["temperature"] = temperature
    active_settings["max_tokens"] = max_tokens

def _get_model(model_name: str):
    """Retrieves a cached GenerativeModel client or initializes a new one."""
    global _api_key
    current_key = _get_api_key()
    
    # Configure API client if key changes or cache is empty
    if not _models_cache or _api_key != current_key:
        genai.configure(api_key=current_key)
        _api_key = current_key
        _models_cache.clear()
        
    if model_name not in _models_cache:
        _models_cache[model_name] = genai.GenerativeModel(model_name)
        
    return _models_cache[model_name]

def ask_gemini(prompt: str) -> str:
    """Sends a prompt to Gemini with the active settings configuration and timeout limits."""
    if not prompt or not prompt.strip():
        raise GeminiError("Prompt cannot be empty.")

    try:
        model_name = active_settings["model_name"]
        temperature = active_settings["temperature"]
        max_tokens = active_settings["max_tokens"]

        model = _get_model(model_name)
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens
        }
        
        # Apply timeout limit (60 seconds) to prevent frozen requests
        response = model.generate_content(
            prompt.strip(),
            generation_config=generation_config,
            request_options={"timeout": 60.0}
        )

        if not response or not response.text:
            raise GeminiError("Gemini returned an empty response. The request may have timed out or failed.")

        return response.text.strip()

    except GeminiError:
        raise
    except Exception as exc:
        raise GeminiError(f"Gemini API error: {exc}") from exc

def is_api_configured() -> bool:
    try:
        _get_api_key()
        return True
    except GeminiError:
        return False

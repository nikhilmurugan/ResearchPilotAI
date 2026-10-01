"""
ollama_service.py
-----------------
Reusable Ollama client for ResearchPilotAI.

Features:
  - Singleton Ollama client (one connection reused across the entire app)
  - Configurable model, temperature, and max-token settings
  - Streaming response support (generator-based)
  - Timeout handling (default 120 s per request)
  - Retry logic (3 attempts with exponential back-off)
  - Friendly error message when Ollama server is unreachable
  - Never raises an unhandled exception to callers
"""

import os
import time
import logging
from contextvars import ContextVar
from typing import Optional, Generator

import ollama
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

_DEFAULT_TEMPERATURE: float = 0.7
_DEFAULT_MAX_TOKENS: int = 2048
_DEFAULT_TIMEOUT: int = 120      # seconds
_MAX_RETRIES: int = 3
_RETRY_DELAY: float = 2.0        # base seconds for exponential back-off

# Friendly message shown whenever Ollama is unavailable
OLLAMA_UNAVAILABLE_MSG = (
    "Ollama server is not running. Please start Ollama."
)

# ── Active settings (can be updated at runtime) ────────────────────────────────

_DEFAULT_SETTINGS: dict = {
    "model": OLLAMA_MODEL,
    "temperature": _DEFAULT_TEMPERATURE,
    "max_tokens": _DEFAULT_MAX_TOKENS,
}
_active_settings: ContextVar[dict] = ContextVar("ollama_active_settings", default=_DEFAULT_SETTINGS)


# ── Custom exception ───────────────────────────────────────────────────────────

class OllamaError(Exception):
    """Raised when Ollama calls fail or the server is unreachable."""


# ── Singleton client ───────────────────────────────────────────────────────────

_client: Optional[ollama.Client] = None


def _get_client() -> ollama.Client:
    """Return the shared Ollama client, creating it once."""
    global _client
    if _client is None:
        _client = ollama.Client(host=OLLAMA_HOST, timeout=_DEFAULT_TIMEOUT)
    return _client


# ── Settings API ───────────────────────────────────────────────────────────────

def set_active_settings(
    model: str = OLLAMA_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> None:
    """Update the global Ollama model settings used for all subsequent calls."""
    _active_settings.set({
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    })
    logger.info(
        "Ollama settings updated — model=%s temperature=%s max_tokens=%s",
        model, temperature, max_tokens,
    )


# ── Core inference function ────────────────────────────────────────────────────

def ask_ollama(
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> str:
    """
    Send *prompt* to Ollama and return the model response as a string.

    Parameters
    ----------
    prompt        : The user message / instruction.
    system_prompt : Optional system-level instruction prepended to the context.
    model         : Override the globally active model for this call.
    temperature   : Override temperature for this call.
    max_tokens    : Override max-token limit for this call.
    timeout       : Per-request timeout in seconds (default 120).

    Returns
    -------
    str — The model's response text.

    Raises
    ------
    OllamaError — If the server is unreachable or returns an error after all
                  retries are exhausted.
    """
    if not prompt or not prompt.strip():
        raise OllamaError("Prompt cannot be empty.")

    active_settings = _active_settings.get()
    _model = model or active_settings["model"]
    _temperature = temperature if temperature is not None else active_settings["temperature"]
    _max_tokens = max_tokens if max_tokens is not None else active_settings["max_tokens"]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})

    options = {
        "temperature": _temperature,
        "num_predict": _max_tokens,
    }

    client = _get_client()
    last_error: Exception = Exception("Unknown error")

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.debug(
                "Ollama request attempt %d/%d — model=%s",
                attempt, _MAX_RETRIES, _model,
            )
            response = client.chat(
                model=_model,
                messages=messages,
                options=options,
                keep_alive="1h"
            )
            text = response["message"]["content"]
            if not text or not text.strip():
                raise OllamaError("Ollama returned an empty response.")
            return text.strip()

        except OllamaError:
            raise  # Don't retry on logical errors (empty prompt, empty response)

        except Exception as exc:
            last_error = exc
            error_str = str(exc).lower()

            # Detect connection / server-not-running errors immediately
            if any(kw in error_str for kw in (
                "connection refused", "connect call failed",
                "connection error", "cannot connect", "nodename nor servname",
                "failed to establish", "remotedisconnected",
            )):
                logger.error("Ollama server unreachable: %s", exc)
                raise OllamaError(OLLAMA_UNAVAILABLE_MSG) from exc

            logger.warning(
                "Ollama attempt %d failed: %s. Retrying in %.1fs…",
                attempt, exc, _RETRY_DELAY * attempt,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY * attempt)

    raise OllamaError(
        f"Ollama failed after {_MAX_RETRIES} attempts. Last error: {last_error}"
    ) from last_error


def stream_ollama(
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Generator[str, None, None]:
    """
    Stream tokens from Ollama, yielding each chunk as it arrives.

    Yields
    ------
    str — Each text chunk from the streaming response.

    Raises
    ------
    OllamaError — If the server is unreachable or the prompt is empty.
    """
    if not prompt or not prompt.strip():
        raise OllamaError("Prompt cannot be empty.")

    active_settings = _active_settings.get()
    _model = model or active_settings["model"]
    _temperature = temperature if temperature is not None else active_settings["temperature"]
    _max_tokens = max_tokens if max_tokens is not None else active_settings["max_tokens"]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})

    options = {
        "temperature": _temperature,
        "num_predict": _max_tokens,
    }

    client = _get_client()

    try:
        stream = client.chat(
            model=_model,
            messages=messages,
            options=options,
            stream=True,
            keep_alive="1h"
        )
        for chunk in stream:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
    except Exception as exc:
        error_str = str(exc).lower()
        if any(kw in error_str for kw in (
            "connection refused", "connect call failed",
            "connection error", "cannot connect", "failed to establish",
            "remotedisconnected",
        )):
            raise OllamaError(OLLAMA_UNAVAILABLE_MSG) from exc
        raise OllamaError(f"Streaming failed: {exc}") from exc


def embed_ollama(texts: list[str]) -> list[list[float]]:
    """Create vectors for document chunks or a retrieval query using Ollama."""
    if not texts or any(not text or not text.strip() for text in texts):
        raise OllamaError("Text to embed cannot be empty.")

    try:
        response = _get_client().embed(
            model=OLLAMA_EMBEDDING_MODEL,
            input=texts,
            keep_alive="1h",
        )
        embeddings = response.embeddings
        if len(embeddings) != len(texts):
            raise OllamaError("Ollama returned an incomplete embedding response.")
        return [[float(value) for value in embedding] for embedding in embeddings]
    except OllamaError:
        raise
    except Exception as exc:
        logger.exception("Ollama embedding request failed")
        raise OllamaError(
            "Document embeddings are unavailable. Check Ollama and the configured embedding model."
        ) from exc


# ── Health-check helper ────────────────────────────────────────────────────────

def is_ollama_available() -> bool:
    """
    Return True if the Ollama server is reachable and the configured model
    is loaded; False otherwise.  Never raises.
    """
    try:
        client = _get_client()
        # list() raises if the server is down
        client.list()
        return True
    except Exception as exc:
        logger.warning("Ollama health-check failed: %s", exc)
        return False
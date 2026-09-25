"""
Thin wrapper around the Groq API.
Handles both LLM chat completions and audio transcription (Whisper)
so the rest of the app never touches the SDK directly.
"""

import os
from functools import lru_cache
from groq import Groq

# Groq retires models regularly. Instead of hard-coding one ID, we ask the API which
# models this key can use and take the first available one from these preference lists.
# Set GROQ_CHAT_MODEL / GROQ_STT_MODEL (env or Streamlit secrets) to force a specific model.
CHAT_MODEL_PREFERENCES = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]
STT_MODEL_PREFERENCES = ["whisper-large-v3-turbo", "whisper-large-v3"]


def get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to a .env file or Streamlit secrets."
        )
    return Groq(api_key=api_key)


@lru_cache(maxsize=1)
def _available_models() -> frozenset:
    try:
        return frozenset(m.id for m in get_client().models.list().data)
    except Exception:
        return frozenset()


def _pick(env_var: str, preferences: list[str], kind: str) -> str:
    forced = os.environ.get(env_var)
    if forced:
        return forced
    available = _available_models()
    if not available:              # listing failed -- try our first choice anyway
        return preferences[0]
    for m in preferences:
        if m in available:
            return m
    raise RuntimeError(
        f"None of the preferred {kind} models are available on Groq anymore: {preferences}. "
        f"Available: {sorted(available)}. Set {env_var} to one of them."
    )


def chat_model() -> str:
    return _pick("GROQ_CHAT_MODEL", CHAT_MODEL_PREFERENCES, "chat")


def stt_model() -> str:
    return _pick("GROQ_STT_MODEL", STT_MODEL_PREFERENCES, "speech-to-text")


def chat(messages: list[dict], temperature: float = 0.7, json_mode: bool = False) -> str:
    """Run a chat completion. messages = [{"role": "user"/"system", "content": "..."}]"""
    client = get_client()
    kwargs = {
        "model": chat_model(),
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Send raw audio bytes to Groq's Whisper endpoint, return plain text transcript."""
    client = get_client()
    transcription = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=stt_model(),
        response_format="text",
    )
    return transcription

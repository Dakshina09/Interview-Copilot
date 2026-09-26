"""
Thin wrapper around the Groq API.
Handles both LLM chat completions and audio transcription (Whisper)
so the rest of the app never touches the SDK directly.
"""

import json
import os
import re
from functools import lru_cache
from groq import Groq, BadRequestError, NotFoundError

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


REASONING_EFFORT = {            # keep hidden reasoning short so it can't eat the output budget
    "openai/gpt-oss": "low",
    "qwen/qwen3": "none",
}


def _reasoning_extra(model: str) -> dict:
    for prefix, effort in REASONING_EFFORT.items():
        if model.startswith(prefix):
            return {"reasoning_effort": effort}
    return {}


def extract_json(text: str) -> str:
    """Pull the JSON object out of a free-text reply (think tags, code fences, prose)."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return ""
    candidate = text[start:end + 1]
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return ""


def _complete(model: str, messages: list[dict], temperature: float, json_mode: bool) -> str:
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": 8192 if json_mode else 2048,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    extra = _reasoning_extra(model)
    if extra:
        kwargs["extra_body"] = extra      # works across groq SDK versions
    response = get_client().chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _fallback_models(current: str) -> list[str]:
    available = _available_models()
    return [m for m in CHAT_MODEL_PREFERENCES
            if m != current and (not available or m in available)]


def chat(messages: list[dict], temperature: float = 0.7, json_mode: bool = False) -> str:
    """Run a chat completion. messages = [{"role": "user"/"system", "content": "..."}]

    With json_mode=True this always returns a JSON string (or "" if every attempt failed):
      1. strict JSON mode on the chosen model
      2. same model, free text + JSON extraction (Groq's JSON validator rejects some
         otherwise-fine outputs, especially from reasoning models)
      3. next available model, same as 2
    """
    model = chat_model()
    if not json_mode:
        return _complete(model, messages, temperature, False)

    try:
        raw = _complete(model, messages, temperature, True)
        if extract_json(raw):
            return extract_json(raw)
    except BadRequestError:
        pass

    nudge = messages + [{"role": "user", "content":
                         "Reply with the JSON object only: no prose, no markdown fences."}]
    for m in [model] + _fallback_models(model)[:2]:
        try:
            out = extract_json(_complete(m, nudge, temperature, False))
            if out:
                return out
        except (BadRequestError, NotFoundError):
            continue
    return ""


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Send raw audio bytes to Groq's Whisper endpoint, return plain text transcript."""
    client = get_client()
    transcription = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=stt_model(),
        response_format="text",
    )
    return transcription

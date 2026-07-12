"""
Thin wrapper around the Groq API.
Handles both LLM chat completions and audio transcription (Whisper)
so the rest of the app never touches the SDK directly.
"""

import os
from groq import Groq

CHAT_MODEL = "llama-3.3-70b-versatile"
STT_MODEL = "whisper-large-v3-turbo"


def get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to a .env file or Streamlit secrets."
        )
    return Groq(api_key=api_key)


def chat(messages: list[dict], temperature: float = 0.7, json_mode: bool = False) -> str:
    """Run a chat completion. messages = [{"role": "user"/"system", "content": "..."}]"""
    client = get_client()
    kwargs = {
        "model": CHAT_MODEL,
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
        model=STT_MODEL,
        response_format="text",
    )
    return transcription

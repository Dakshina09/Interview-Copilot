"""Given a just-transcribed chunk of interview audio, produce quick glance-able talking
points instead of a full answer -- this is meant to jog the candidate's memory during a
real conversation, not to be read verbatim."""

from core.groq_client import chat

SYSTEM_PROMPT = """You are a real-time interview assist. You receive a live transcript
snippet of an interviewer's question (it may be incomplete or slightly garbled from
speech-to-text). Respond with 3-5 short bullet points (max 8 words each) the candidate
can glance at while answering out loud themselves. Ground bullets in the candidate's
resume when relevant. Never write full sentences or a scripted answer -- just cue words
and structure (e.g. "Start with the STAR situation", "Mention the 40% latency drop").
Plain text bullets only, one per line, no numbering, no preamble."""


def get_live_hints(transcript_snippet: str, resume_context: str = "") -> str:
    user_prompt = f"""INTERVIEWER SAID: {transcript_snippet}

CANDIDATE BACKGROUND: {resume_context[:1500]}"""

    return chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
    )

import os
import streamlit as st
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder
from core.groq_client import transcribe_audio
from core.live_assist import get_live_hints

load_dotenv()
st.set_page_config(page_title="Live Assist", page_icon="🎙️", layout="wide")
st.title("🎙️ Live Assist")
st.caption(
    "Record the interviewer's question as it's asked. You get quick cue-card bullets, "
    "not a scripted answer -- meant to jog your memory while you speak for yourself."
)

if "live_log" not in st.session_state:
    st.session_state.live_log = []

resume_context = st.session_state.get("resume_text", "")
if not resume_context:
    st.info("No resume loaded -- hints will be generic. Load one on the Resume + JD Analysis page for personalized cues.")

audio = mic_recorder(start_prompt="🎙️ Record question", stop_prompt="⏹️ Stop", key="live_recorder")

if audio:
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY in your .env file first.")
    else:
        with st.spinner("Transcribing..."):
            transcript = transcribe_audio(audio["bytes"], "question.wav")
        with st.spinner("Generating cues..."):
            hints = get_live_hints(transcript, resume_context)
        st.session_state.live_log.insert(0, {"transcript": transcript, "hints": hints})

for entry in st.session_state.live_log:
    st.markdown(f"**Heard:** _{entry['transcript']}_")
    st.markdown("**Cues:**")
    st.success(entry["hints"])
    st.divider()

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI Interview Copilot", page_icon="🎯", layout="wide")

st.title("🎯 AI Interview Copilot")
st.caption("Resume-aware interview prep: generate questions, practice with feedback, get live assist.")

if not os.environ.get("GROQ_API_KEY"):
    st.warning(
        "GROQ_API_KEY not found. Create a `.env` file (copy `.env.example`) with your "
        "free key from console.groq.com, then restart the app."
    )
else:
    st.success("Groq API key detected. You're good to go.")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📄 Resume + JD Analysis")
    st.write(
        "Upload your resume and paste a job description. Get a tailored set of "
        "likely interview questions with model answers, grounded in your actual "
        "projects and the role's requirements."
    )
    st.page_link("pages/1_Resume_JD_Analysis.py", label="Open", icon="➡️")

with col2:
    st.subheader("🎯 Practice Mode")
    st.write(
        "Answer questions (typed or spoken) and get scored feedback across "
        "relevance, structure (STAR), specificity, and communication -- plus a "
        "tightened rewrite of your answer."
    )
    st.page_link("pages/2_Practice_Mode.py", label="Open", icon="➡️")

with col3:
    st.subheader("🎙️ Live Assist")
    st.write(
        "Record a live interviewer question, get instant glance-able talking "
        "point bullets grounded in your resume -- a real-time cue card, not a "
        "scripted answer."
    )
    st.page_link("pages/3_Live_Assist.py", label="Open", icon="➡️")

st.divider()
st.caption(
    "Built with Streamlit + Groq (Llama 3.3 70B for reasoning, Whisper Large v3 Turbo for speech-to-text)."
)

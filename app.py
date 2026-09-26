import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI Career Readiness Platform", page_icon="🎯", layout="wide")

st.title("🎯 AI Career Readiness Platform")
st.caption("Resume intelligence + interview copilot: find your gaps against a job, close them, then prove it in practice.")

if not os.environ.get("GROQ_API_KEY"):
    st.warning(
        "GROQ_API_KEY not found. Create a `.env` file (copy `.env.example`) with your "
        "free key from console.groq.com, then restart the app."
    )
else:
    st.success("Groq API key detected. You're good to go.")

st.divider()

PAGES = [
    ("🧭 Profile & Match", "pages/1_Profile_and_Match.py",
     "Resume → structured profile (skills, experience, projects) → per-skill match "
     "against a job description, with a plain-English explanation of your gaps."),
    ("🗺️ Skill Gap Plan", "pages/2_Skill_Gap_Plan.py",
     "Turn the gaps into a week-by-week learning plan that builds on projects you've "
     "already done."),
    ("📄 Interview Questions", "pages/3_Interview_Questions.py",
     "Tailored questions with model answers -- weighted toward your weakest skills and "
     "tagged with the skill each one tests."),
    ("🎯 Practice Mode", "pages/4_Practice_Mode.py",
     "Answer typed or spoken, get LLM-as-judge feedback. Scores feed back into the skill "
     "they test, so you can see claimed vs. shown."),
    ("📝 Tailored Resume", "pages/6_Tailored_Resume.py",
     "Pull your GitHub projects, rewrite your resume for this job, check every claim "
     "against its source, and export a one-page LaTeX / PDF."),
    ("🎙️ Live Assist", "pages/5_Live_Assist.py",
     "Record a live interviewer question and get glance-able cue bullets grounded in your "
     "resume -- a memory jog, not a script."),
]

st.markdown("**Flow:** Resume + JD → Match → Gap plan → Targeted questions → Practice → updated skill scores → Tailored resume")

for row in (PAGES[:3], PAGES[3:]):
    cols = st.columns(3)
    for col, (title, path, desc) in zip(cols, row):
        with col:
            st.subheader(title)
            st.write(desc)
            st.page_link(path, label="Open", icon="➡️")

st.divider()
st.caption(
    "Built with Streamlit + Groq (auto-selected open LLM for reasoning, Whisper for speech-to-text) + fastembed (bge-small) for matching."
)

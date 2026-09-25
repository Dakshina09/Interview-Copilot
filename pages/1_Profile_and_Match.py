import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from core.resume_parser import extract_text_from_pdf
from core.profile_extractor import extract_profile
from core.jd_parser import parse_jd
from core.matcher import match, explain_gaps
from core.embeddings import backend_name
from core.state import init_state

load_dotenv()
st.set_page_config(page_title="Profile & Match", page_icon="🧭", layout="wide")
init_state()
st.title("🧭 Profile & Job Match")
st.caption("Resume → structured profile → per-skill match against the job description.")

col1, col2 = st.columns(2)
with col1:
    uploaded = st.file_uploader("Upload resume (PDF)", type=["pdf"])
    if uploaded and st.session_state.get("_resume_file_id") != uploaded.file_id:
        st.session_state.resume_text = extract_text_from_pdf(uploaded)
        st.session_state._resume_file_id = uploaded.file_id
        st.session_state.profile = None
        st.session_state.match = None
    if st.session_state.resume_text:
        st.success(f"Resume loaded ({len(st.session_state.resume_text)} characters).")
with col2:
    jd_text = st.text_area("Paste job description", value=st.session_state.jd_text, height=250)

can_run = bool(st.session_state.resume_text and jd_text.strip())
if st.button("Analyze Match", type="primary", disabled=not can_run):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY in your .env file first.")
    else:
        st.session_state.jd_text = jd_text
        with st.spinner("Extracting structured profile from resume..."):
            st.session_state.profile = extract_profile(st.session_state.resume_text)
        with st.spinner("Parsing job requirements..."):
            st.session_state.job = parse_jd(jd_text)
        with st.spinner("Matching (embeddings)..."):
            st.session_state.match = match(st.session_state.profile, st.session_state.job)
        # downstream results depend on this match -> reset them
        st.session_state.learning_plan = None
        st.session_state.generated_questions = []

profile, job, result = st.session_state.profile, st.session_state.job, st.session_state.match
if not result:
    st.stop()

if not result.skill_scores:
    st.warning("Couldn't extract any skills from the job description. Try pasting the full JD.")
    st.stop()

st.divider()
if backend_name() == "lexical":
    st.warning("Embedding model unavailable -- using lexical fallback matching. Scores are less semantic.")

m1, m2, m3 = st.columns(3)
m1.metric("Overall match", f"{result.overall:.0%}")
req = [s for s in result.skill_scores if s.required]
m2.metric("Required skills covered", f"{sum(s.resume_score >= 0.5 for s in req)}/{len(req)}")
if result.responsibilities:
    m3.metric("Responsibilities covered",
              f"{sum(r.score >= 0.5 for r in result.responsibilities)}/{len(result.responsibilities)}")

# ---- per-skill bars ---------------------------------------------------------
st.subheader(f"Skill match{' — ' + job.title if job.title else ''}")
scores = list(reversed(result.skill_scores))   # plotly draws bottom-up
fig = go.Figure(go.Bar(
    x=[s.resume_score * 100 for s in scores],
    y=[f"{s.skill}{'' if s.required else ' (nice)'}" for s in scores],
    orientation="h",
    text=[f"{s.resume_score:.0%}" for s in scores],
    textposition="outside",
    marker_color=["#2E7D6B" if s.resume_score >= 0.7 else "#C98A1B" if s.resume_score >= 0.5 else "#B5473A"
                  for s in scores],
    customdata=[s.best_evidence for s in scores],
    hovertemplate="%{y}: %{x:.0f}%<br>Closest evidence: %{customdata}<extra></extra>",
))
fig.update_layout(xaxis=dict(range=[0, 110], title="Match %"), height=max(250, 32 * len(scores)),
                  margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")
st.caption("Green ≥ 70% · Amber 50–69% · Red < 50%. Hover a bar to see which resume line it matched.")

# ---- gap explanation ----------------------------------------------------
gaps = explain_gaps(result)
if gaps:
    st.subheader("Why you're not a full match")
    for line in gaps:
        st.markdown(f"- {line}")
    st.page_link("pages/2_Skill_Gap_Plan.py", label="Build a learning plan for these gaps", icon="➡️")
else:
    st.success("No major skill gaps against this JD.")

# ---- claimed vs shown ---------------------------------------------------
practiced = [s for s in result.skill_scores if s.interview_score is not None]
if practiced:
    st.subheader("Claimed vs. shown")
    st.caption("Resume match vs. how you actually answered questions on that skill in Practice Mode.")
    st.dataframe(pd.DataFrame([{
        "Skill": s.skill,
        "Resume match": f"{s.resume_score:.0%}",
        "Interview score": f"{s.interview_score:.0%}",
        "Attempts": len(s.interview_scores),
        "Flag": "⚠️ claimed but not shown" if s.resume_score >= 0.7 and s.interview_score < 0.5 else "",
    } for s in practiced]), hide_index=True, width="stretch")

# ---- details --------------------------------------------------------------
with st.expander("Responsibility coverage"):
    for r in result.responsibilities:
        st.markdown(f"**{r.score:.0%}** — {r.text}")
        if r.missing_skills:
            st.caption(f"Missing: {', '.join(r.missing_skills)}")
        elif r.best_evidence:
            st.caption(f"Closest evidence: {r.best_evidence}")

with st.expander("Extracted candidate profile"):
    st.json(profile.to_dict())
with st.expander("Extracted job requirements"):
    st.json(job.to_dict())

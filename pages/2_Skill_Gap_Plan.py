import os
import streamlit as st
from dotenv import load_dotenv
from core.gap_planner import build_plan
from core.state import init_state

load_dotenv()
st.set_page_config(page_title="Skill Gap Plan", page_icon="🗺️", layout="wide")
init_state()
st.title("🗺️ Skill Gap → Learning Plan")
st.caption("Target role → required skills → your current skills → gaps → a plan that builds on what you already have.")

result = st.session_state.match
if not result:
    st.info("Run an analysis first.")
    st.page_link("pages/1_Profile_and_Match.py", label="Go to Profile & Match", icon="➡️")
    st.stop()

threshold = st.slider("Treat skills below this match as gaps", 0.3, 0.9, 0.5, 0.05, format="%.2f")
include_interview = st.checkbox(
    "Also include skills I scored below 50% on in Practice Mode", value=True,
    help="Catches skills your resume claims but you couldn't explain in an interview answer.",
)

gaps = result.gaps(threshold)
if include_interview:
    weak_in_interview = [s for s in result.skill_scores
                         if s not in gaps and s.interview_score is not None and s.interview_score < 0.5]
    gaps = gaps + weak_in_interview

if not gaps:
    st.success("No gaps at this threshold.")
    st.stop()

st.markdown("**Gaps:** " + ", ".join(
    f"{g.skill} ({g.resume_score:.0%}{'' if g.required else ', nice-to-have'})" for g in gaps))
weeks = st.slider("Weeks available", 2, 16, 8)

if st.button("Generate Learning Plan", type="primary"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY in your .env file first.")
    else:
        with st.spinner("Building your plan..."):
            st.session_state.learning_plan = build_plan(
                st.session_state.profile, st.session_state.job, gaps, weeks)

plan = st.session_state.learning_plan
if plan:
    if plan.get("error"):
        st.error(plan["error"])
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Duration", f"{plan.get('total_weeks', '?')} weeks")
    c2.metric("Suggested effort", f"{plan.get('hours_per_week', '?')} hrs/week")

    for item in plan.get("plan", []):
        with st.container(border=True):
            st.markdown(f"### {item.get('skill', '')}  ·  {item.get('priority', '')} priority")
            st.write(item.get("why", ""))
            if item.get("builds_on"):
                st.caption(f"Builds on: {item['builds_on']}")
            for step in item.get("steps", []):
                st.markdown(f"- **Week {step.get('week', '?')}:** {step.get('task', '')}"
                            + (f"  _({step['resource']})_" if step.get("resource") else ""))
            if item.get("project_idea"):
                st.info(f"Portfolio project: {item['project_idea']}")

    md = [f"# Learning plan — {st.session_state.job.title or 'target role'}\n"]
    for item in plan.get("plan", []):
        md.append(f"## {item.get('skill')} ({item.get('priority')})\n{item.get('why', '')}\n")
        md += [f"- Week {s.get('week')}: {s.get('task')} ({s.get('resource', '')})" for s in item.get("steps", [])]
        md.append(f"\n**Project:** {item.get('project_idea', '')}\n")
    st.download_button("Download plan (.md)", "\n".join(md), file_name="learning_plan.md")

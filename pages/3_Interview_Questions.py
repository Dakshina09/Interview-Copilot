import os
import streamlit as st
from dotenv import load_dotenv
from core.question_gen import generate_questions
from core.state import init_state

load_dotenv()
st.set_page_config(page_title="Interview Questions", page_icon="📄", layout="wide")
init_state()
st.title("📄 Interview Questions")

result = st.session_state.match
if not result:
    st.info("Analyze your resume against a job description first -- questions are built from that match.")
    st.page_link("pages/1_Profile_and_Match.py", label="Go to Profile & Match", icon="➡️")
    st.stop()

gaps = [g.skill for g in result.gaps()]
jd_skills = [s.skill for s in result.skill_scores]

num_q = st.slider("Number of questions", min_value=5, max_value=20, value=10)
target_gaps = st.checkbox(
    f"Target my weak skills ({', '.join(gaps) if gaps else 'none found'})",
    value=bool(gaps), disabled=not gaps,
)

if st.button("Generate Questions", type="primary"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY in your .env file first.")
    else:
        with st.spinner("Generating questions from your profile and the JD..."):
            st.session_state.generated_questions = generate_questions(
                st.session_state.resume_text, st.session_state.jd_text, num_q,
                jd_skills=jd_skills, focus_skills=gaps if target_gaps else None,
            )

if st.session_state.generated_questions:
    st.divider()
    st.subheader(f"{len(st.session_state.generated_questions)} Generated Questions")
    st.caption("These carry over into Practice Mode. Scores there feed back into each question's skill.")

    categories = sorted(set(q["category"] for q in st.session_state.generated_questions))
    tabs = st.tabs(["All"] + categories)

    def render_question(q, idx):
        skill = f" · tests {q['target_skill']}" if q.get("target_skill") else ""
        with st.expander(f"Q{idx + 1}. [{q['category']}] {q['question']}"):
            st.caption(f"Why asked: {q['why_asked']}{skill}")
            st.markdown("**Model answer:**")
            st.write(q["model_answer"])

    with tabs[0]:
        for i, q in enumerate(st.session_state.generated_questions):
            render_question(q, i)

    for tab, cat in zip(tabs[1:], categories):
        with tab:
            for i, q in enumerate(st.session_state.generated_questions):
                if q["category"] == cat:
                    render_question(q, i)

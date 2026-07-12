import os
import streamlit as st
from dotenv import load_dotenv
from core.resume_parser import extract_text_from_pdf
from core.question_gen import generate_questions

load_dotenv()
st.set_page_config(page_title="Resume + JD Analysis", page_icon="📄", layout="wide")
st.title("📄 Resume + JD Analysis")

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "generated_questions" not in st.session_state:
    st.session_state.generated_questions = []

col1, col2 = st.columns(2)

with col1:
    uploaded = st.file_uploader("Upload resume (PDF)", type=["pdf"])
    if uploaded:
        st.session_state.resume_text = extract_text_from_pdf(uploaded)
        st.success(f"Extracted {len(st.session_state.resume_text)} characters.")
        with st.expander("Preview extracted text"):
            st.text(st.session_state.resume_text[:2000])

with col2:
    jd_text = st.text_area("Paste job description", height=250)

num_q = st.slider("Number of questions", min_value=5, max_value=20, value=10)

if st.button("Generate Questions", type="primary", disabled=not st.session_state.resume_text or not jd_text):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY in your .env file first.")
    else:
        with st.spinner("Analyzing resume against job description..."):
            st.session_state.generated_questions = generate_questions(
                st.session_state.resume_text, jd_text, num_q
            )
            st.session_state.jd_text = jd_text

if st.session_state.generated_questions:
    st.divider()
    st.subheader(f"{len(st.session_state.generated_questions)} Generated Questions")
    st.caption("These carry over into Practice Mode and Live Assist automatically.")

    categories = sorted(set(q["category"] for q in st.session_state.generated_questions))
    tabs = st.tabs(["All"] + categories)

    def render_question(q, idx):
        with st.expander(f"Q{idx + 1}. [{q['category']}] {q['question']}"):
            st.caption(f"Why asked: {q['why_asked']}")
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

import os
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder
from core.groq_client import transcribe_audio
from core.evaluator import evaluate_answer

load_dotenv()
st.set_page_config(page_title="Practice Mode", page_icon="🎯", layout="wide")
st.title("🎯 Practice Mode")

if "generated_questions" not in st.session_state:
    st.session_state.generated_questions = []
if "score_history" not in st.session_state:
    st.session_state.score_history = []

DEFAULT_QUESTIONS = [
    {"category": "Behavioral", "question": "Tell me about a challenging bug you debugged.",
     "why_asked": "Generic fallback", "model_answer": ""},
    {"category": "Behavioral", "question": "Describe a time you disagreed with a teammate.",
     "why_asked": "Generic fallback", "model_answer": ""},
    {"category": "Technical", "question": "Walk me through how you'd design a rate limiter.",
     "why_asked": "Generic fallback", "model_answer": ""},
]

question_pool = st.session_state.generated_questions or DEFAULT_QUESTIONS
if not st.session_state.generated_questions:
    st.info("No custom questions yet -- using generic fallback questions. Generate your own on the Resume + JD Analysis page.")

labels = [f"[{q['category']}] {q['question']}" for q in question_pool]
selected_idx = st.selectbox("Pick a question", range(len(labels)), format_func=lambda i: labels[i])
question = question_pool[selected_idx]["question"]

st.markdown(f"### {question}")

input_mode = st.radio("Answer via", ["Type", "Record audio"], horizontal=True)

answer_text = ""
if input_mode == "Type":
    answer_text = st.text_area("Your answer", height=180)
else:
    audio = mic_recorder(start_prompt="🎙️ Start recording", stop_prompt="⏹️ Stop", key="practice_recorder")
    if audio:
        with st.spinner("Transcribing..."):
            answer_text = transcribe_audio(audio["bytes"], "answer.wav")
        st.text_area("Transcript (edit if needed)", value=answer_text, height=150, key="edited_transcript")
        answer_text = st.session_state.get("edited_transcript", answer_text)

if st.button("Get Feedback", type="primary", disabled=not answer_text):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY in your .env file first.")
    else:
        with st.spinner("Scoring your answer..."):
            resume_context = st.session_state.get("resume_text", "")
            result = evaluate_answer(question, answer_text, resume_context)
            st.session_state.score_history.append(
                {"question": question, "score": result["overall_score"]}
            )

        st.divider()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Overall", f"{result['overall_score']}/10")
        m2.metric("Relevance", f"{result['relevance']}/10")
        m3.metric("Structure", f"{result['structure']}/10")
        m4.metric("Specificity", f"{result['specificity']}/10")
        m5.metric("Communication", f"{result['communication']}/10")

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=[result["relevance"], result["structure"], result["specificity"], result["communication"]],
            theta=["Relevance", "Structure", "Specificity", "Communication"],
            fill="toself",
        ))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)

        col_s, col_i = st.columns(2)
        with col_s:
            st.markdown("**Strengths**")
            for s in result["strengths"]:
                st.markdown(f"- {s}")
        with col_i:
            st.markdown("**Improvements**")
            for imp in result["improvements"]:
                st.markdown(f"- {imp}")

        st.markdown("**Suggested tightened rewrite:**")
        st.info(result["suggested_rewrite"])

if len(st.session_state.score_history) > 1:
    st.divider()
    st.subheader("Progress")
    scores = [h["score"] for h in st.session_state.score_history]
    fig2 = go.Figure(data=go.Scatter(y=scores, mode="lines+markers"))
    fig2.update_layout(yaxis=dict(range=[0, 10]), xaxis_title="Attempt", yaxis_title="Overall score", height=300)
    st.plotly_chart(fig2, use_container_width=True)

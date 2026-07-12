"""LLM-as-judge scoring for a candidate's spoken/typed answer to an interview question."""

import json
from core.groq_client import chat

SYSTEM_PROMPT = """You are a strict but fair interview coach. Score the candidate's answer
to the given question on a 0-10 scale across four dimensions: relevance, structure
(STAR method for behavioral, clarity of approach for technical), specificity (concrete
details/numbers vs vague claims), and communication (conciseness, confidence).

Return ONLY a JSON object of this exact shape:
{
  "overall_score": 0-10,
  "relevance": 0-10,
  "structure": 0-10,
  "specificity": 0-10,
  "communication": 0-10,
  "strengths": ["short bullet", "short bullet"],
  "improvements": ["short actionable bullet", "short actionable bullet"],
  "suggested_rewrite": "a tightened 3-5 sentence version of their answer"
}
No markdown, no commentary, valid JSON only."""


def evaluate_answer(question: str, answer: str, resume_context: str = "") -> dict:
    user_prompt = f"""QUESTION: {question}

CANDIDATE'S ANSWER: {answer}

CANDIDATE BACKGROUND (for context, don't repeat verbatim): {resume_context[:1500]}"""

    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        json_mode=True,
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "overall_score": 0,
            "relevance": 0,
            "structure": 0,
            "specificity": 0,
            "communication": 0,
            "strengths": [],
            "improvements": ["Evaluator failed to parse response, try again."],
            "suggested_rewrite": "",
        }

"""Generate likely interview questions (with model answers) from a resume + job description."""

import json
from core.groq_client import chat

SYSTEM_PROMPT = """You are a senior technical interviewer. Given a candidate's resume and a
job description, generate a realistic set of interview questions the candidate is likely
to face, tailored specifically to their background and the role.

Return ONLY a JSON object of this exact shape:
{
  "questions": [
    {
      "category": "Behavioral" | "Technical" | "Project-Specific" | "System Design" | "Resume Gap",
      "question": "string",
      "why_asked": "one line on why an interviewer would ask this",
      "model_answer": "a strong, concise model answer using the candidate's actual background, 4-6 sentences"
    }
  ]
}
No markdown, no commentary, valid JSON only."""


def generate_questions(resume_text: str, jd_text: str, num_questions: int = 10) -> list[dict]:
    user_prompt = f"""RESUME:
{resume_text[:6000]}

JOB DESCRIPTION:
{jd_text[:3000]}

Generate exactly {num_questions} questions, mixing categories, ordered roughly from
easier/behavioral to harder/technical. Ground every question in specifics from the
resume (real project names, tools, numbers) and the JD (required skills)."""

    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        json_mode=True,
    )

    try:
        data = json.loads(raw)
        return data.get("questions", [])
    except json.JSONDecodeError:
        return []

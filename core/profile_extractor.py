"""Resume text -> structured CandidateProfile (Groq JSON mode)."""

import json
from core.groq_client import chat
from core.schemas import CandidateProfile

SYSTEM_PROMPT = """You extract a structured candidate profile from resume text.
Only include what the resume actually states -- never invent skills, employers or numbers.

For each skill, "evidence" must be a short quote or close paraphrase of the resume line
that shows the skill being USED (a project, job bullet, or course). If the skill only
appears in a skills list with no usage, set evidence to "".

Return ONLY a JSON object of this exact shape:
{
  "name": "string",
  "summary": "one-line professional summary",
  "skills": [{"name": "Python", "category": "Language|ML|Data|Cloud|Tool|Framework|Soft|Other", "evidence": "string"}],
  "experience": [{"title": "string", "organization": "string", "duration": "string", "highlights": ["string"]}],
  "projects": [{"name": "string", "description": "one or two lines", "tech": ["string"]}]
}
Use canonical skill names (e.g. "PyTorch" not "pytorch lib"). No markdown, valid JSON only."""


def extract_profile(resume_text: str) -> CandidateProfile:
    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"RESUME:\n{resume_text[:8000]}"},
        ],
        temperature=0.1,
        json_mode=True,
    )
    try:
        return CandidateProfile.from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return CandidateProfile()

"""Job description text -> structured JobProfile (Groq JSON mode)."""

import json
from core.groq_client import chat
from core.schemas import JobProfile

SYSTEM_PROMPT = """You extract structured requirements from a job description.

- "must_have": skills/technologies the JD states as required.
- "nice_to_have": skills described as preferred, a plus, or bonus.
- "responsibilities": each day-to-day responsibility, with the skills (from the two
  lists above, using the SAME names) that the responsibility needs.

Use short canonical skill names ("AWS", "Docker", "Machine Learning", "SQL").
Keep each list to at most 12 items. Only include what the JD says.

Return ONLY a JSON object of this exact shape:
{
  "title": "string",
  "must_have": ["string"],
  "nice_to_have": ["string"],
  "responsibilities": [{"text": "string", "skills": ["string"]}]
}
No markdown, valid JSON only."""


def parse_jd(jd_text: str) -> JobProfile:
    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"JOB DESCRIPTION:\n{jd_text[:5000]}"},
        ],
        temperature=0.1,
        json_mode=True,
    )
    try:
        return JobProfile.from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return JobProfile()

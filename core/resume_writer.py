"""
Resume + selected GitHub repos + JD -> tailored resume content (Groq JSON mode).

The LLM only *selects and rephrases*. Every bullet must carry the source text it came
from, and claim_checker.py verifies numbers and technologies afterwards.
"""

from __future__ import annotations
import json

from core.groq_client import chat
from core.github_ingest import Repo
from core.schemas import JobProfile, SkillScore

SYSTEM_PROMPT = """You tailor a candidate's resume to a job description.

HARD RULES (a violation makes the resume unusable):
1. Use ONLY facts found in the RESUME or the GITHUB REPOS text. Never invent numbers,
   metrics, users, employers, dates, awards or technologies.
2. You MAY rephrase using the job description's vocabulary, but only when the source
   supports it (e.g. source says "built a chatbot over PDFs with FAISS" -> "built a
   retrieval-augmented generation (RAG) pipeline" is fine).
3. Do NOT claim any skill listed under MISSING SKILLS unless the source text proves it.
4. Every bullet includes "source": the exact phrase from the resume/README it is based on.
5. Bullets: start with a strong past-tense verb, one line to 1.5 lines (max ~25 words),
   what you built + how + result/impact if the source states one. No em dashes.
6. Order projects and bullets by relevance to the job, most relevant first.

Return ONLY a JSON object of this exact shape:
{
  "header": {"name": "", "email": "", "phone": "", "location": "",
             "links": [{"label": "GitHub", "url": ""}]},
  "summary": "2 lines max, tailored to the role, or empty string",
  "education": [{"school": "", "degree": "", "dates": "", "details": ""}],
  "experience": [{"title": "", "organization": "", "location": "", "dates": "",
                  "bullets": [{"text": "", "source": ""}]}],
  "projects": [{"name": "", "link": "", "tech": [""],
                "bullets": [{"text": "", "source": ""}]}],
  "skills": [{"category": "", "items": [""]}],
  "achievements": [{"text": "", "source": ""}]
}
Header, education and achievements come from the RESUME only. Leave a field "" if unknown.
No markdown, valid JSON only."""


def write_resume(resume_text: str, repos: list[Repo], job: JobProfile,
                 gaps: list[SkillScore], max_projects: int = 4) -> dict:
    repo_blocks = "\n\n".join(
        f"### REPO: {r.name}\nURL: {r.url}\n{r.source_text()[:2500]}" for r in repos
    )
    user_prompt = f"""TARGET ROLE: {job.title or 'unspecified'}
MUST-HAVE SKILLS: {', '.join(job.must_have)}
NICE-TO-HAVE: {', '.join(job.nice_to_have)}
RESPONSIBILITIES:
{chr(10).join('- ' + r.text for r in job.responsibilities)}

MISSING SKILLS (do not claim): {', '.join(g.skill for g in gaps) or 'none'}

RESUME:
{resume_text[:7000]}

GITHUB REPOS (preferred source for the Projects section):
{repo_blocks or '(none selected)'}

Pick the {max_projects} most relevant projects (GitHub repos first, then resume projects).
Up to 3 bullets per project and 4 per experience entry. Use the repo URL as "link"."""

    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        json_mode=True,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Could not parse the generated resume. Try again."}
    return _normalize(data)


def _normalize(d: dict) -> dict:
    """Make sure every expected key exists with the right type."""
    def bullets(items):
        out = []
        for b in items or []:
            if isinstance(b, str):
                b = {"text": b, "source": ""}
            if b.get("text", "").strip():
                out.append({"text": b["text"].strip(), "source": b.get("source", "")})
        return out

    header = d.get("header") or {}
    return {
        "header": {
            "name": header.get("name", ""), "email": header.get("email", ""),
            "phone": header.get("phone", ""), "location": header.get("location", ""),
            "links": [l for l in header.get("links", []) or [] if l.get("url")],
        },
        "summary": d.get("summary", "") or "",
        "education": d.get("education", []) or [],
        "experience": [dict(e, bullets=bullets(e.get("bullets"))) for e in d.get("experience", []) or []],
        "projects": [dict(p, bullets=bullets(p.get("bullets")), tech=p.get("tech") or [])
                     for p in d.get("projects", []) or []],
        "skills": [s for s in d.get("skills", []) or [] if s.get("items")],
        "achievements": bullets(d.get("achievements")),
    }

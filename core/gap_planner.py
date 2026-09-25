"""Skill gaps -> personalized learning plan (Groq JSON mode)."""

import json
from core.groq_client import chat
from core.schemas import CandidateProfile, JobProfile, SkillScore

SYSTEM_PROMPT = """You are a pragmatic career mentor for AI/ML and software roles.
Given a candidate's existing skills and projects, a target role, and the skills they are
missing, write a focused learning plan that BUILDS ON what they already know
(e.g. "containerize your existing churn-prediction API with Docker").

Rules:
- Prioritize required skills over nice-to-have.
- Each skill gets 2-4 concrete weekly steps and ONE portfolio project idea that extends
  one of the candidate's existing projects where possible.
- Name well-known resources (official docs, well-known courses) by name only. No URLs.
- Be realistic about time: hours_per_week is for a full-time student.

Return ONLY a JSON object of this exact shape:
{
  "total_weeks": int,
  "hours_per_week": int,
  "plan": [
    {
      "skill": "string",
      "priority": "High" | "Medium" | "Low",
      "why": "one line tying it to the target role",
      "builds_on": "which existing skill/project this leverages",
      "steps": [{"week": int, "task": "string", "resource": "string"}],
      "project_idea": "string"
    }
  ]
}
No markdown, valid JSON only."""


def build_plan(profile: CandidateProfile, job: JobProfile, gaps: list[SkillScore],
               weeks: int = 8) -> dict:
    if not gaps:
        return {"total_weeks": 0, "hours_per_week": 0, "plan": []}

    gap_lines = "\n".join(
        f"- {g.skill} ({'required' if g.required else 'nice-to-have'}, "
        f"current match {g.resume_score:.0%}"
        + (f", interview score {g.interview_score:.0%}" if g.interview_score is not None else "")
        + ")"
        for g in gaps
    )
    user_prompt = f"""TARGET ROLE: {job.title or 'unspecified'}

CANDIDATE SKILLS: {', '.join(s.name for s in profile.skills)}
CANDIDATE PROJECTS: {'; '.join(f"{p.name} ({', '.join(p.tech)})" for p in profile.projects)}

SKILL GAPS:
{gap_lines}

Fit the plan into about {weeks} weeks."""

    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        json_mode=True,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"total_weeks": 0, "hours_per_week": 0, "plan": [], "error": "Could not parse plan."}

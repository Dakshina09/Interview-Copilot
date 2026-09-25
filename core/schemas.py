"""
Shared data structures. Every page reads/writes these through st.session_state,
so the resume analysis, gap plan, question generator and practice scorer all
talk about the *same* skills.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class Skill:
    name: str
    category: str = "Other"          # Language / ML / Cloud / Tool / Soft / Other
    evidence: str = ""               # resume line that supports the claim


@dataclass
class Experience:
    title: str
    organization: str = ""
    duration: str = ""
    highlights: list[str] = field(default_factory=list)


@dataclass
class Project:
    name: str
    description: str = ""
    tech: list[str] = field(default_factory=list)


@dataclass
class CandidateProfile:
    name: str = ""
    summary: str = ""
    skills: list[Skill] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateProfile":
        return cls(
            name=d.get("name", "") or "",
            summary=d.get("summary", "") or "",
            skills=[Skill(**_pick(s, Skill)) for s in d.get("skills", []) if s.get("name")],
            experience=[Experience(**_pick(e, Experience)) for e in d.get("experience", []) if e.get("title")],
            projects=[Project(**_pick(p, Project)) for p in d.get("projects", []) if p.get("name")],
        )

    def evidence_corpus(self) -> list[str]:
        """Every sentence-sized piece of evidence the matcher can compare a JD skill against."""
        items = []
        for s in self.skills:
            items.append(s.name)
            if s.evidence:
                items.append(f"{s.name}: {s.evidence}")
        for p in self.projects:
            items.append(f"{p.name}: {p.description} (tech: {', '.join(p.tech)})")
        for e in self.experience:
            for h in e.highlights:
                items.append(f"{e.title} at {e.organization}: {h}")
        return [i for i in items if i.strip()]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Responsibility:
    text: str
    skills: list[str] = field(default_factory=list)   # JD skills this responsibility needs


@dataclass
class JobProfile:
    title: str = ""
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    responsibilities: list[Responsibility] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "JobProfile":
        return cls(
            title=d.get("title", "") or "",
            must_have=[s for s in d.get("must_have", []) if s],
            nice_to_have=[s for s in d.get("nice_to_have", []) if s],
            responsibilities=[
                Responsibility(text=r.get("text", ""), skills=r.get("skills", []) or [])
                for r in d.get("responsibilities", []) if r.get("text")
            ],
        )

    def all_skills(self) -> list[tuple[str, bool]]:
        """(skill, is_required) pairs, de-duplicated, must-haves first."""
        seen, out = set(), []
        for s, req in [(s, True) for s in self.must_have] + [(s, False) for s in self.nice_to_have]:
            key = s.lower().strip()
            if key not in seen:
                seen.add(key)
                out.append((s, req))
        return out

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkillScore:
    skill: str
    required: bool
    resume_score: float              # 0-1, from the matcher
    best_evidence: str = ""          # closest resume item
    responsibilities_needing: int = 0
    interview_scores: list[float] = field(default_factory=list)   # 0-1, from Practice Mode

    @property
    def interview_score(self) -> float | None:
        if not self.interview_scores:
            return None
        return sum(self.interview_scores) / len(self.interview_scores)


@dataclass
class ResponsibilityCoverage:
    text: str
    score: float                     # 0-1
    best_evidence: str = ""
    missing_skills: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    skill_scores: list[SkillScore]
    responsibilities: list[ResponsibilityCoverage]
    overall: float                   # 0-1

    def gaps(self, threshold: float = 0.5) -> list[SkillScore]:
        """Skills below threshold, required ones first, weakest first."""
        g = [s for s in self.skill_scores if s.resume_score < threshold]
        return sorted(g, key=lambda s: (not s.required, s.resume_score))


def _pick(d: dict, cls) -> dict:
    """Keep only keys the dataclass knows about -- LLMs like to add extra fields."""
    allowed = cls.__dataclass_fields__.keys()
    return {k: v for k, v in d.items() if k in allowed and v is not None}

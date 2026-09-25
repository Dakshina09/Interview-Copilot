"""
Deterministic job matching: CandidateProfile x JobProfile -> MatchResult.

No LLM in this step -- scores come from embeddings + exact-match rules, so the same
inputs always give the same numbers and the method can be evaluated (see eval/).

Per-skill score
  1.00  skill in the extracted skill list AND backed by usage evidence
  0.90  skill mentioned verbatim in a project / experience line
  0.85  skill in the extracted skill list, only as a keyword
  else  calibrated cosine similarity against every resume evidence item

Overall = 0.7 * weighted skill score (must-have x2) + 0.3 * responsibility coverage
"""

from __future__ import annotations
import re
import numpy as np
from core.embeddings import similarity_matrix, backend_name
from core.schemas import (
    CandidateProfile, JobProfile, MatchResult, SkillScore, ResponsibilityCoverage,
)

# Cosine -> 0-1 calibration. Tuned for bge-small-en-v1.5; re-fit with
# `python -m eval.run_eval --calibrate` against your own labeled pairs.
SKILL_LOW, SKILL_HIGH = 0.55, 0.80
RESP_LOW, RESP_HIGH = 0.50, 0.75
# Char-trigram TF-IDF fallback lives on a very different scale.
LEX_SKILL_LOW, LEX_SKILL_HIGH = 0.15, 0.50
LEX_RESP_LOW, LEX_RESP_HIGH = 0.10, 0.40

CLAIMED_WITH_EVIDENCE = 1.0
CLAIMED_NO_EVIDENCE = 0.85
MENTIONED_IN_EVIDENCE = 0.90
MUST_HAVE_WEIGHT = 2.0
SKILL_WEIGHT, RESP_WEIGHT = 0.7, 0.3

ALIASES = {
    "ml": "machine learning", "dl": "deep learning", "nlp": "natural language processing",
    "cv": "computer vision", "k8s": "kubernetes", "js": "javascript", "ts": "typescript",
    "amazon web services": "aws", "google cloud": "gcp", "google cloud platform": "gcp",
    "postgres": "postgresql", "sklearn": "scikit-learn", "llms": "llm",
    "large language models": "llm", "genai": "generative ai", "ci/cd": "cicd", "ci cd": "cicd",
}


def normalize_skill(s: str) -> str:
    s = re.sub(r"\s+", " ", s.lower().strip().rstrip("."))
    return ALIASES.get(s, s)


def calibrate(cos: np.ndarray | float, low: float, high: float):
    return np.clip((np.asarray(cos) - low) / (high - low), 0.0, 1.0)


def _mentioned(key: str, corpus: list[str]) -> str:
    """Return the first evidence line that names the skill as a whole word/phrase."""
    pat = re.compile(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])")
    for line in corpus:
        if pat.search(line.lower()):
            return line
    return ""


def match(profile: CandidateProfile, job: JobProfile,
          skill_low: float | None = None, skill_high: float | None = None) -> MatchResult:
    lexical = backend_name() == "lexical"
    if skill_low is None:
        skill_low = LEX_SKILL_LOW if lexical else SKILL_LOW
    if skill_high is None:
        skill_high = LEX_SKILL_HIGH if lexical else SKILL_HIGH
    resp_low, resp_high = (LEX_RESP_LOW, LEX_RESP_HIGH) if lexical else (RESP_LOW, RESP_HIGH)

    jd_skills = job.all_skills()
    corpus = profile.evidence_corpus()

    claimed = {normalize_skill(s.name): s for s in profile.skills}

    # --- per-skill scores -------------------------------------------------
    sims = similarity_matrix([s for s, _ in jd_skills], corpus) if corpus else None
    skill_scores: list[SkillScore] = []
    for i, (skill, required) in enumerate(jd_skills):
        key = normalize_skill(skill)
        if key in claimed:
            c = claimed[key]
            score = CLAIMED_WITH_EVIDENCE if c.evidence else CLAIMED_NO_EVIDENCE
            best = c.evidence or f"Listed in skills: {c.name}"
        elif line := _mentioned(key, corpus):
            score, best = MENTIONED_IN_EVIDENCE, line
        elif sims is not None and sims.shape[1]:
            j = int(np.argmax(sims[i]))
            score = float(calibrate(sims[i, j], skill_low, skill_high))
            best = corpus[j] if score > 0 else ""
        else:
            score, best = 0.0, ""

        needing = sum(
            1 for r in job.responsibilities
            if key in {normalize_skill(x) for x in r.skills}
        )
        skill_scores.append(SkillScore(skill, required, round(score, 3), best, needing))

    # --- responsibility coverage -----------------------------------------
    score_by_skill = {normalize_skill(s.skill): s.resume_score for s in skill_scores}
    resp_cov: list[ResponsibilityCoverage] = []
    if job.responsibilities:
        rs = similarity_matrix([r.text for r in job.responsibilities], corpus) if corpus else None
        for i, r in enumerate(job.responsibilities):
            if rs is not None and rs.shape[1]:
                j = int(np.argmax(rs[i]))
                sem = float(calibrate(rs[i, j], resp_low, resp_high))
                best = corpus[j]
            else:
                sem, best = 0.0, ""
            linked = [score_by_skill.get(normalize_skill(s)) for s in r.skills]
            linked = [x for x in linked if x is not None]
            # blend: what the text says + whether the skills it needs are present
            score = 0.5 * sem + 0.5 * (sum(linked) / len(linked)) if linked else sem
            missing = [s for s in r.skills if score_by_skill.get(normalize_skill(s), 1.0) < 0.5]
            resp_cov.append(ResponsibilityCoverage(r.text, round(score, 3), best, missing))

    # --- overall ------------------------------------------------------------
    if skill_scores:
        w = np.array([MUST_HAVE_WEIGHT if s.required else 1.0 for s in skill_scores])
        v = np.array([s.resume_score for s in skill_scores])
        skill_part = float((w * v).sum() / w.sum())
    else:
        skill_part = 0.0
    if resp_cov:
        overall = SKILL_WEIGHT * skill_part + RESP_WEIGHT * float(np.mean([r.score for r in resp_cov]))
    else:
        overall = skill_part

    return MatchResult(skill_scores, resp_cov, round(overall, 3))


def explain_gaps(result: MatchResult, threshold: float = 0.5) -> list[str]:
    """Plain-English, fully deterministic gap explanations."""
    n_resp = len(result.responsibilities)
    lines = []
    for g in result.gaps(threshold):
        kind = "required" if g.required else "nice-to-have"
        if g.responsibilities_needing and n_resp:
            lines.append(
                f"**{g.skill}** ({kind}, {g.resume_score:.0%} match) is needed in "
                f"{g.responsibilities_needing} of {n_resp} listed responsibilities."
            )
        else:
            lines.append(f"**{g.skill}** ({kind}) has only a {g.resume_score:.0%} match with your resume.")
    return lines

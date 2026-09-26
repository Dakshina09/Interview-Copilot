"""Rank GitHub repos (and resume projects) by relevance to a JobProfile."""

from __future__ import annotations
from dataclasses import dataclass, field

import numpy as np

from core.embeddings import similarity_matrix
from core.github_ingest import Repo
from core.matcher import normalize_skill, _mentioned
from core.schemas import JobProfile


@dataclass
class RankedRepo:
    repo: Repo
    score: float                       # 0-1
    skills_shown: list[str] = field(default_factory=list)


def rank_repos(repos: list[Repo], job: JobProfile) -> list[RankedRepo]:
    """
    score = 0.6 * semantic similarity (repo text vs. JD requirements)
          + 0.4 * share of JD skills the repo explicitly mentions
    Repos with no README and no description are pushed down: nothing to write from.
    """
    if not repos:
        return []
    jd_skills = [s for s, _ in job.all_skills()]
    queries = jd_skills + [r.text for r in job.responsibilities]
    docs = [r.source_text()[:2000] for r in repos]

    sims = similarity_matrix(queries, docs) if queries else np.zeros((0, len(repos)))
    # semantic: average of each repo's best-matching requirements (top 5)
    semantic = []
    for j in range(len(repos)):
        col = np.sort(sims[:, j])[::-1][:5] if sims.shape[0] else np.array([0.0])
        semantic.append(float(col.mean()))
    semantic = np.array(semantic)
    if semantic.max() > semantic.min():
        semantic = (semantic - semantic.min()) / (semantic.max() - semantic.min())
    else:
        semantic = np.zeros_like(semantic)

    ranked = []
    for j, repo in enumerate(repos):
        text = [repo.source_text().lower()]
        shown = [s for s in jd_skills if _mentioned(normalize_skill(s), text)]
        coverage = len(shown) / len(jd_skills) if jd_skills else 0.0
        score = 0.6 * semantic[j] + 0.4 * coverage
        if not repo.readme and not repo.description:
            score *= 0.3
        ranked.append(RankedRepo(repo, round(float(score), 3), shown))
    return sorted(ranked, key=lambda r: r.score, reverse=True)

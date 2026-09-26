"""
Deterministic hallucination check for generated resume bullets.

For each bullet we look up the source text of the item it belongs to (the matching
GitHub repo's README, or the original resume) and flag:
  * numbers / percentages / multipliers that don't appear in that source
  * technologies (from the JD, the profile, or a common-tech list) that don't appear there
Flagged bullets are shown to the user and excluded from the PDF unless they approve them.
"""

from __future__ import annotations
import re

from core.github_ingest import Repo
from core.matcher import normalize_skill, _mentioned

COMMON_TECH = [
    "python", "java", "c++", "javascript", "typescript", "sql", "r", "go", "rust", "matlab",
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost", "lightgbm", "pandas", "numpy",
    "spark", "hadoop", "airflow", "kafka", "docker", "kubernetes", "aws", "gcp", "azure",
    "fastapi", "flask", "django", "streamlit", "react", "node.js", "postgresql", "mysql",
    "mongodb", "redis", "faiss", "langchain", "llamaindex", "hugging face", "transformers",
    "openai", "groq", "llm", "rag", "bert", "gpt", "lstm", "cnn", "rnn", "opencv", "yolo",
    "mlflow", "git", "linux", "tableau", "power bi", "excel", "whisper", "selenium",
]

_NUM = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(%|x\b|k\b|\+)?", re.I)


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _numbers(text: str) -> list[str]:
    return [m.group(1).replace(",", "") for m in _NUM.finditer(text)]


def _source_for(item_name: str, repos: list[Repo], resume_text: str) -> str:
    key = _norm_key(item_name)
    for r in repos:
        rk = _norm_key(r.name)
        if rk and (rk in key or key in rk):
            return (r.source_text() + "\n" + resume_text).lower()
    return resume_text.lower()


def check_bullet(text: str, source: str, vocab: list[str]) -> list[str]:
    flags = []
    src_nums = set(_numbers(source))
    for n in _numbers(text):
        if n not in src_nums:
            flags.append(f"number '{n}' not found in source")
    for term in vocab:
        key = normalize_skill(term)
        if len(key) < 2:
            continue
        if _mentioned(key, [text.lower()]) and not _mentioned(key, [source]):
            flags.append(f"'{term}' not found in source")
    return flags


def check_resume(resume: dict, repos: list[Repo], resume_text: str,
                 vocab_extra: list[str]) -> dict:
    """Adds 'flags' (list[str]) and 'keep' (bool) to every bullet. Returns summary counts."""
    vocab = sorted({*COMMON_TECH, *[v.lower() for v in vocab_extra if v]}, key=len, reverse=True)
    total = flagged = 0

    def run(bullets, source):
        nonlocal total, flagged
        for b in bullets:
            b["flags"] = check_bullet(b["text"], source, vocab)
            b["keep"] = not b["flags"]
            total += 1
            flagged += bool(b["flags"])

    for p in resume.get("projects", []):
        run(p["bullets"], _source_for(p.get("name", ""), repos, resume_text))
        src = _source_for(p.get("name", ""), repos, resume_text)
        p["tech_flags"] = [t for t in p.get("tech", []) if not _mentioned(normalize_skill(t), [src])]
    for e in resume.get("experience", []):
        run(e["bullets"], resume_text.lower())
    run(resume.get("achievements", []), resume_text.lower())

    everything = (resume_text + "\n" + "\n".join(r.source_text() for r in repos)).lower()
    for group in resume.get("skills", []):
        group["flags"] = [i for i in group.get("items", [])
                          if not _mentioned(normalize_skill(i), [everything])]
    return {"total": total, "flagged": flagged}

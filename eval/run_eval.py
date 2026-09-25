"""
Evaluate the matcher against hand-labeled resume/skill pairs.

    python -m eval.run_eval              # report metrics with current thresholds
    python -m eval.run_eval --calibrate  # grid-search SKILL_LOW / SKILL_HIGH

Labels are your own 0-100 judgement of "how well does this resume show this skill".
The JD skill list is taken from the labels (the JD parser is bypassed) so this measures
the *matcher* alone. Profiles are extracted once with the LLM and cached in eval/.cache/.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from core.matcher import match
from core.schemas import CandidateProfile, JobProfile
from core.embeddings import backend_name

HERE = Path(__file__).parent
CACHE = HERE / ".cache"
GAP_THRESHOLD = 0.5


def load_profile(pair: dict) -> CandidateProfile:
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{pair['id']}.json"
    if f.exists():
        return CandidateProfile.from_dict(json.loads(f.read_text()))
    from core.profile_extractor import extract_profile
    profile = extract_profile(pair["resume_text"])
    f.write_text(json.dumps(profile.to_dict(), indent=2))
    return profile


def spearman(a, b) -> float:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def evaluate(pairs, profiles, low, high):
    pred, gold = [], []
    for pair, profile in zip(pairs, profiles):
        job = JobProfile(
            must_have=[s["skill"] for s in pair["skills"] if s["required"]],
            nice_to_have=[s["skill"] for s in pair["skills"] if not s["required"]],
        )
        result = match(profile, job, skill_low=low, skill_high=high)
        by_skill = {s.skill: s.resume_score for s in result.skill_scores}
        for s in pair["skills"]:
            pred.append(by_skill.get(s["skill"], 0.0))
            gold.append(s["label"] / 100)
    pred, gold = np.array(pred), np.array(gold)

    pg, gg = pred < GAP_THRESHOLD, gold < GAP_THRESHOLD
    tp = int((pg & gg).sum())
    precision = tp / pg.sum() if pg.sum() else float("nan")
    recall = tp / gg.sum() if gg.sum() else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else float("nan")
    return {
        "n_skills": len(gold),
        "mae": float(np.abs(pred - gold).mean()),
        "spearman": spearman(pred, gold),
        "gap_precision": precision,
        "gap_recall": recall,
        "gap_f1": f1,
    }


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "labeled_pairs.json"))
    ap.add_argument("--calibrate", action="store_true")
    args = ap.parse_args()

    pairs = json.loads(Path(args.data).read_text())
    profiles = [load_profile(p) for p in pairs]
    print(f"Embedding backend: {backend_name()}  |  pairs: {len(pairs)}")

    m = evaluate(pairs, profiles, None, None)
    print("\nCurrent thresholds (core/matcher.py defaults for this backend)")
    for k, v in m.items():
        print(f"  {k:14s} {v:.3f}" if isinstance(v, float) else f"  {k:14s} {v}")

    if args.calibrate:
        best = None
        for low in np.arange(0.05, 0.76, 0.025):
            for high in np.arange(low + 0.10, 0.96, 0.025):
                r = evaluate(pairs, profiles, float(low), float(high))
                if best is None or r["mae"] < best[2]["mae"]:
                    best = (float(low), float(high), r)
        low, high, r = best
        print(f"\nBest thresholds by MAE: SKILL_LOW={low:.3f}, SKILL_HIGH={high:.3f}")
        for k, v in r.items():
            print(f"  {k:14s} {v:.3f}" if isinstance(v, float) else f"  {k:14s} {v}")
        print("\nUpdate SKILL_LOW / SKILL_HIGH in core/matcher.py if these generalize "
              "(with few pairs, beware overfitting -- hold some pairs out).")


if __name__ == "__main__":
    main()

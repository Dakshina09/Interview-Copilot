"""Session-state helpers shared by every page."""

import streamlit as st
from core.matcher import normalize_skill

DEFAULTS = {
    "resume_text": "",
    "jd_text": "",
    "profile": None,          # CandidateProfile
    "job": None,              # JobProfile
    "match": None,            # MatchResult
    "learning_plan": None,    # dict from gap_planner
    "generated_questions": [],
    "score_history": [],
}


def init_state():
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v.copy() if isinstance(v, list) else v


def record_interview_score(skill: str, overall_score_0_10: float) -> bool:
    """Feed a Practice Mode score back into the matching skill. Returns True if a skill matched."""
    match = st.session_state.get("match")
    if not match or not skill:
        return False
    key = normalize_skill(skill)
    for s in match.skill_scores:
        if normalize_skill(s.skill) == key:
            s.interview_scores.append(overall_score_0_10 / 10)
            return True
    return False

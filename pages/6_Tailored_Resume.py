import html
import os
import urllib.parse
import uuid

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core.claim_checker import check_resume
from core.github_ingest import fetch_repos, find_github_in_text, GitHubError
from core.latex_render import build_one_page, compiler_available, render
from core.project_ranker import rank_repos
from core.resume_writer import write_resume
from core.state import init_state

load_dotenv()
st.set_page_config(page_title="Tailored Resume", page_icon="📝", layout="wide")
init_state()
for k in ("ranked_repos", "tailored", "tailored_tex", "tailored_pdf"):
    st.session_state.setdefault(k, None)

st.title("📝 Tailored Resume")
st.caption("Resume + GitHub projects + job description → a one-page LaTeX resume, "
           "with every claim checked against its source.")

result = st.session_state.match
if not result:
    st.info("Run Profile & Match first -- the resume is tailored to that job description.")
    st.page_link("pages/1_Profile_and_Match.py", label="Go to Profile & Match", icon="➡️")
    st.stop()

job, profile = st.session_state.job, st.session_state.profile


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch(username: str):
    return fetch_repos(username)


# ---- 1. GitHub projects -------------------------------------------------------
st.subheader("1. Pick projects from GitHub")
default_user = find_github_in_text(st.session_state.resume_text)
c1, c2 = st.columns([3, 1])
username = c1.text_input("GitHub username or profile URL", value=default_user)
if c2.button("Fetch repos", disabled=not username, width="stretch"):
    try:
        with st.spinner("Reading your public repos and READMEs..."):
            repos = _fetch(username)
        with st.spinner("Ranking against the job description..."):
            st.session_state.ranked_repos = rank_repos(repos, job)
            st.session_state.repo_fetch_id = uuid.uuid4().hex[:8]
        st.session_state.tailored = None
    except GitHubError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Couldn't reach GitHub: {e}")

ranked = st.session_state.ranked_repos
selected_repos = []
if ranked:
    df = pd.DataFrame([{
        "Include": i < 4 and r.score > 0.2,
        "Repo": r.repo.name,
        "Relevance": round(r.score * 100),
        "JD skills shown": ", ".join(r.skills_shown),
        "README": "yes" if r.repo.readme else "no",
    } for i, r in enumerate(ranked)])
    edited = st.data_editor(
        df, hide_index=True, width="stretch",
        key=f"repo_picker_{st.session_state.get('repo_fetch_id', '')}",
        disabled=["Repo", "Relevance", "JD skills shown", "README"],
        column_config={"Relevance": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")},
    )
    selected_repos = [r.repo for r, inc in zip(ranked, edited["Include"]) if inc]
    st.caption(f"{len(selected_repos)} selected. Repos without a README give the writer little to work with.")
else:
    st.caption("Optional: skip this to tailor using only the projects already on your resume.")

# ---- 2. Generate -----------------------------------------------------------------
st.subheader("2. Generate")
max_projects = st.slider("Projects on the resume", 2, 5, 4)
if st.button("Generate tailored resume", type="primary"):
    if not os.environ.get("GROQ_API_KEY"):
        st.error("Set GROQ_API_KEY first.")
    else:
        with st.spinner("Writing a tailored resume from your sources..."):
            tailored = write_resume(st.session_state.resume_text, selected_repos, job,
                                    result.gaps(), max_projects)
        if tailored.get("error"):
            st.error(tailored["error"])
        else:
            vocab = [s for s, _ in job.all_skills()] + [s.name for s in profile.skills]
            tailored["_check"] = check_resume(tailored, selected_repos,
                                              st.session_state.resume_text, vocab)
            tailored["_gen"] = uuid.uuid4().hex[:8]    # fresh widget keys per generation
            st.session_state.tailored = tailored
            st.session_state.tailored_tex = st.session_state.tailored_pdf = None

tailored = st.session_state.tailored
if not tailored:
    st.stop()

# ---- 3. Review -------------------------------------------------------------------
st.subheader("3. Review")
chk = tailored.get("_check", {})
if chk.get("flagged"):
    st.warning(f"{chk['flagged']} of {chk['total']} bullets mention a number or technology that "
               "isn't in the source they came from. They're unticked and left out of the PDF. "
               "Tick one only if it's true.")
else:
    st.success(f"All {chk.get('total', 0)} bullets trace back to your resume or READMEs.")


gen = tailored.get("_gen", "")


def review_bullets(bullets, key_prefix):
    key_prefix = f"{gen}_{key_prefix}"
    for i, b in enumerate(bullets):
        label = b["text"] + ("" if not b.get("flags") else "  ⚠️ " + "; ".join(b["flags"]))
        b["keep"] = st.checkbox(label, value=b.get("keep", True), key=f"{key_prefix}_{i}",
                                help=f"Source: {b.get('source') or 'n/a'}")


if tailored.get("summary"):
    tailored["summary"] = st.text_area("Summary", tailored["summary"], height=70, key=f"{gen}_summary")

for pi, p in enumerate(tailored.get("projects", [])):
    with st.container(border=True):
        st.markdown(f"**{p.get('name', '')}**  ·  {', '.join(p.get('tech', []))}")
        if p.get("tech_flags"):
            st.caption(f"Dropped from tech list (not in source): {', '.join(p['tech_flags'])}")
        review_bullets(p["bullets"], f"p{pi}")

for ei, e in enumerate(tailored.get("experience", [])):
    with st.container(border=True):
        st.markdown(f"**{e.get('title', '')}**, {e.get('organization', '')}")
        review_bullets(e["bullets"], f"e{ei}")

if tailored.get("achievements"):
    with st.container(border=True):
        st.markdown("**Achievements**")
        review_bullets(tailored["achievements"], "a")

dropped_skills = [i for g in tailored.get("skills", []) for i in g.get("flags", [])]
if dropped_skills:
    st.caption(f"Skills dropped (not found in resume or repos): {', '.join(dropped_skills)}")

# ---- 4. Export --------------------------------------------------------------------
st.subheader("4. Export")
compiler = compiler_available()
if st.button("Build PDF" if compiler else "Build LaTeX", type="primary"):
    with st.spinner("Rendering and fitting to one page..."):
        if compiler:
            tex, pdf, log, trimmed = build_one_page(tailored)
            st.session_state.tailored_tex, st.session_state.tailored_pdf = tex, pdf
            if pdf is None:
                st.error("LaTeX compile failed. The .tex is still available below.")
                with st.expander("Compiler log"):
                    st.code(log)
            elif trimmed:
                st.info("Trimmed to fit one page: " + " | ".join(t[:60] + "..." for t in trimmed))
        else:
            st.session_state.tailored_tex = render(tailored)

tex = st.session_state.tailored_tex
if tex:
    name = (tailored["header"].get("name") or "resume").replace(" ", "_")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Download .tex", tex, file_name=f"{name}_resume.tex", width="stretch")
    if st.session_state.tailored_pdf:
        c2.download_button("Download PDF", st.session_state.tailored_pdf,
                           file_name=f"{name}_resume.pdf", mime="application/pdf", width="stretch")
    elif not compiler:
        c2.caption("No LaTeX compiler here. Use Overleaf to get the PDF.")
    with c3:
        # The .tex is fully HTML-escaped (and URL-encoded) before going into the form,
        # so LLM-written text can't inject markup into this iframe.
        overleaf_form = (
            f"""<form action="https://www.overleaf.com/docs" method="post" target="_blank" style="margin:0">
            <input type="hidden" name="encoded_snip" value="{html.escape(urllib.parse.quote(tex))}">
            <input type="hidden" name="snip_name" value="{html.escape(name)}_resume.tex">
            <button type="submit" style="width:100%;padding:0.45rem;border:1px solid #ccc;
              border-radius:0.5rem;background:#fff;cursor:pointer;font-size:0.95rem">Open in Overleaf</button>
            </form>""")
        if hasattr(st, "iframe"):
            st.iframe(overleaf_form, height=48)
        else:                                   # older Streamlit
            import streamlit.components.v1 as components
            components.html(overleaf_form, height=48)
    with st.expander("LaTeX source"):
        st.code(tex, language="latex")

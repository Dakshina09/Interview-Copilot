"""
Tailored resume dict -> LaTeX source -> PDF.

Only standard packages (geometry, hyperref, xcolor, lmodern) so it compiles on a basic
TeX Live install (see packages.txt for Streamlit Cloud). If no LaTeX compiler is
installed, the app still offers the .tex download and an "Open in Overleaf" button.
"""

from __future__ import annotations
import copy
import re
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
_UNICODE = {"\u2013": "--", "\u2014": "--", "\u2019": "'", "\u2018": "'", "\u201c": "``",
            "\u201d": "''", "\u2022": "", "\u2192": r"$\rightarrow$", "\u00a0": " ",
            "\u2026": "...", "\u2248": r"$\approx$", "\u00d7": r"$\times$"}


def esc(text) -> str:
    """Escape LaTeX specials first, then map common Unicode to LaTeX (order matters:
    the replacements contain backslashes that must not be escaped again)."""
    text = "".join(_SPECIAL.get(ch, ch) for ch in str(text or ""))
    for k, v in _UNICODE.items():
        text = text.replace(k, v)
    # drop anything pdflatex + T1 can't typeset (emoji, CJK, ...)
    return "".join(c for c in text if ord(c) < 256)


def esc_url(url: str) -> str:
    return str(url or "").replace("%", r"\%").replace("#", r"\#").replace("\\", "")


def _pretty_url(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url or "").rstrip("/")


PREAMBLE = r"""\documentclass[10pt,letterpaper]{article}
% T1 + Latin Modern when available (vector fonts); plain Computer Modern otherwise
\IfFileExists{lmodern.sty}{\usepackage[T1]{fontenc}\usepackage{lmodern}}{}
\usepackage[margin=0.55in,top=0.45in,bottom=0.45in]{geometry}
\usepackage[hidelinks]{hyperref}
\usepackage{xcolor}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\raggedright
\newcommand{\ressection}[1]{\vspace{6pt}{\large\bfseries\uppercase{#1}}\par\vspace{1pt}\hrule\vspace{3pt}}
\newcommand{\entry}[4]{\textbf{#1}\hfill #2\par\ifx&#3&\else{\itshape #3}\hfill{\itshape #4}\par\fi}
\newenvironment{bullets}{\vspace{-4pt}\begin{itemize}\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}\setlength{\topsep}{1pt}\setlength{\partopsep}{0pt}\setlength{\leftmargin}{12pt}}{\end{itemize}\vspace{2pt}}
\begin{document}
"""


def _bullets(items: list[dict]) -> str:
    kept = [b for b in items if b.get("keep", True)]
    if not kept:
        return ""
    return "\\begin{bullets}\n" + "\n".join(f"  \\item {esc(b['text'])}" for b in kept) + "\n\\end{bullets}\n"


def render(resume: dict) -> str:
    h = resume.get("header", {})
    parts = [PREAMBLE]

    parts.append(f"\\begin{{center}}{{\\LARGE\\bfseries {esc(h.get('name'))}}}\\par\\vspace{{3pt}}\n")
    contact = [esc(x) for x in (h.get("phone"), h.get("location")) if x]
    if h.get("email"):
        contact.insert(0, f"\\href{{mailto:{esc_url(h['email'])}}}{{{esc(h['email'])}}}")
    for link in h.get("links", []):
        contact.append(f"\\href{{{esc_url(link['url'])}}}{{{esc(_pretty_url(link['url']))}}}")
    parts.append(" $|$ ".join(contact) + "\n\\end{center}\n\\vspace{-4pt}\n")

    if resume.get("summary"):
        parts.append(f"\\ressection{{Summary}}\n{esc(resume['summary'])}\\par\n")

    if resume.get("education"):
        parts.append("\\ressection{Education}\n")
        for e in resume["education"]:
            parts.append(f"\\entry{{{esc(e.get('school'))}}}{{{esc(e.get('dates'))}}}"
                         f"{{{esc(e.get('degree'))}}}{{}}\n")
            if e.get("details"):
                parts.append(f"{esc(e['details'])}\\par\n")
            parts.append("\\vspace{2pt}\n")

    exp = [e for e in resume.get("experience", []) if any(b.get("keep", True) for b in e["bullets"])]
    if exp:
        parts.append("\\ressection{Experience}\n")
        for e in exp:
            parts.append(f"\\entry{{{esc(e.get('title'))}}}{{{esc(e.get('dates'))}}}"
                         f"{{{esc(e.get('organization'))}}}{{{esc(e.get('location'))}}}\n")
            parts.append(_bullets(e["bullets"]))

    projects = [p for p in resume.get("projects", []) if any(b.get("keep", True) for b in p["bullets"])]
    if projects:
        parts.append("\\ressection{Projects}\n")
        for p in projects:
            tech = [t for t in p.get("tech", []) if t not in p.get("tech_flags", [])]
            title = f"\\textbf{{{esc(p.get('name'))}}}"
            if tech:
                title += f" $|$ {{\\itshape {esc(', '.join(tech))}}}"
            link = (f"\\href{{{esc_url(p['link'])}}}{{\\small {esc(_pretty_url(p['link']))}}}"
                    if p.get("link") else "")
            parts.append(f"{title}\\hfill {link}\\par\n")
            parts.append(_bullets(p["bullets"]))

    skills = resume.get("skills", [])
    if skills:
        parts.append("\\ressection{Technical Skills}\n")
        for g in skills:
            items = [i for i in g.get("items", []) if i not in g.get("flags", [])]
            if items:
                parts.append(f"\\textbf{{{esc(g.get('category'))}:}} {esc(', '.join(items))}\\par\n")

    ach = [a for a in resume.get("achievements", []) if a.get("keep", True)]
    if ach:
        parts.append("\\ressection{Achievements}\n" + _bullets(ach))

    parts.append("\\end{document}\n")
    return "".join(parts)


def compiler_available() -> str | None:
    for c in ("pdflatex", "xelatex"):
        if shutil.which(c):
            return c
    return None


def compile_pdf(tex: str) -> tuple[bytes | None, str]:
    """Returns (pdf_bytes or None, log tail)."""
    exe = compiler_available()
    if not exe:
        return None, "No LaTeX compiler installed."
    with tempfile.TemporaryDirectory() as d:
        Path(d, "resume.tex").write_text(tex, encoding="utf-8")
        try:
            proc = subprocess.run([exe, "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
                                  cwd=d, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return None, "LaTeX compile timed out."
        pdf = Path(d, "resume.pdf")
        if proc.returncode != 0 or not pdf.exists():
            return None, (proc.stdout or "")[-2500:]
        return pdf.read_bytes(), ""


def page_count(pdf: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(BytesIO(pdf)).pages)


def _trim_once(resume: dict) -> bool:
    """Remove the least important kept content. Returns False if nothing left to trim."""
    def kept(bs):
        return [b for b in bs if b.get("keep", True)]

    projects = [p for p in resume.get("projects", []) if kept(p["bullets"])]
    # 1. last bullet of the lowest-ranked project that still has >1
    for p in reversed(projects):
        if len(kept(p["bullets"])) > 1:
            kept(p["bullets"])[-1]["keep"] = False
            return True
    # 2. achievements
    if kept(resume.get("achievements", [])):
        kept(resume["achievements"])[-1]["keep"] = False
        return True
    # 3. experience bullets beyond 2
    for e in reversed(resume.get("experience", [])):
        if len(kept(e["bullets"])) > 2:
            kept(e["bullets"])[-1]["keep"] = False
            return True
    # 4. drop the lowest-ranked project entirely (keep at least 2)
    if len(projects) > 2:
        for b in projects[-1]["bullets"]:
            b["keep"] = False
        return True
    # 5. summary
    if resume.get("summary"):
        resume["summary"] = ""
        return True
    return False


def build_one_page(resume: dict, max_iters: int = 15) -> tuple[str, bytes | None, str, list[str]]:
    """Render + compile, trimming until it fits on one page.
    Returns (tex, pdf, error_log, list of trimmed bullet texts)."""
    resume = copy.deepcopy(resume)
    before = _kept_texts(resume)
    tex = render(resume)
    pdf, log = compile_pdf(tex)
    for _ in range(max_iters):
        if pdf is None or page_count(pdf) <= 1:
            break
        if not _trim_once(resume):
            break
        tex = render(resume)
        pdf, log = compile_pdf(tex)
    trimmed = [t for t in before if t not in _kept_texts(resume)]
    return tex, pdf, log, trimmed


def _kept_texts(resume: dict) -> list[str]:
    out = []
    for sec in ("experience", "projects"):
        for item in resume.get(sec, []):
            out += [b["text"] for b in item["bullets"] if b.get("keep", True)]
    out += [a["text"] for a in resume.get("achievements", []) if a.get("keep", True)]
    if resume.get("summary"):
        out.append("[summary] " + resume["summary"])
    return out


# AI Career Readiness Platform
*Resume intelligence + AI Interview Copilot*
 
Turns a resume into a structured candidate profile, scores it skill-by-skill against a job description, explains the gaps, builds a learning plan to close them, and then tests you on those exact skills in a mock interview. Your interview scores feed back into each skill, so you can see what your resume **claims** vs. what you can actually **show**.
 
### Live demo: [Live Link](https://interview-copilot-4keka9wmap96eadzdsyxy2.streamlit.app/)
 
---
 
## Why I built this
 
Generic interview prep ("tell me about yourself") doesn't map to a specific role or a specific candidate's actual background. This tool closes that gap: every question and every piece of feedback is grounded in the candidate's real resume and the actual job description, not a static question bank.
 
## Features

###  Profile & Match
Resume PDF → structured profile (skills with supporting evidence, experience, projects). The JD is parsed into must-have / nice-to-have skills and responsibilities. Each JD skill gets a **match %** from a deterministic matcher (exact-match rules + local embeddings, no LLM opinion), shown as a bar chart with the resume line each score came from. Gaps are explained in plain English, e.g. *"Docker (required, 12% match) is needed in 3 of 5 listed responsibilities."*

###  Skill Gap Plan
Gaps (plus skills you scored poorly on in practice) → a week-by-week learning plan that builds on projects you already have, with one portfolio project idea per skill. Downloadable as Markdown.

###  Interview Questions
Tailored questions with model answers. About 40% target your weakest skills, and every question is tagged with the skill it tests.

###  Practice Mode
Answer by typing or speaking (Whisper). An LLM-as-judge scores relevance, structure (STAR), specificity and communication. The score is written back to the question's skill, which powers the **claimed vs. shown** table on the Profile & Match page.

###  Live Assist
Record a live interviewer question and get short cue-card bullets grounded in your resume: a memory jog, not a script.

## Tech Stack
 
| Layer | Choice | Why |
|---|---|---|
| UI | Streamlit (multi-page) | Fast to build, matches rest of my portfolio |
| LLM reasoning | Groq — `llama-3.3-70b-versatile` | Free tier, low latency, forced JSON mode for reliable structured output |
| Speech-to-text | Groq — `whisper-large-v3-turbo` | Same API/key as the LLM calls — no second provider to manage |
| PDF parsing | `pypdf` | Lightweight resume text extraction |
| Audio capture | `streamlit-mic-recorder` | In-browser mic recording, no extra backend needed |
| Charts | `plotly` | Skill-match bars, radar chart for answer scores, progress line |
| Embeddings | `fastembed` — `BAAI/bge-small-en-v1.5` | Groq has no embeddings API; fastembed runs ONNX locally with no PyTorch, keeping cloud builds light. Falls back to char n-gram TF-IDF if the model can't download |
 
## Architecture

```
Resume PDF ─► resume_parser ─► profile_extractor (LLM, JSON) ─► CandidateProfile ─┐
                                                                                   ├─► matcher (embeddings + rules) ─► MatchResult
Job Desc ─────────────────────► jd_parser (LLM, JSON) ─────────► JobProfile ───────┘        │
                                                                                            ├─► gap_planner (LLM) ─► learning plan
                                                                                            └─► question_gen (LLM) ─► skill-tagged questions
                                                                                                        │
User answer (text/audio) ─► [Whisper] ─► evaluator (LLM-as-judge) ─► score ─► written back to that skill in MatchResult
Live audio ─► Whisper ─► live_assist ─► cue bullets
```

LLMs do the **extraction** (unstructured text → typed dataclasses in `core/schemas.py`); the **scoring** is deterministic, so identical inputs always give identical numbers and the matcher can be evaluated against labels.

All LLM calls funnel through a single `core/groq_client.py` wrapper — one place that owns the API key, model names, and JSON-mode handling, so every feature stays consistent and easy to swap models later.
 
## Engineering notes (things I'd highlight in an interview)
 
- **Structured output reliability:** both question generation and answer evaluation force `response_format: json_object` on the Groq call and defensively `json.loads()` with a fallback, instead of trusting free-text LLM output to parse cleanly — the same lesson I hit building an LLM benchmarking harness, where unparsed scores silently broke downstream aggregation.
- **Single API surface:** using Groq for both chat completions and Whisper transcription avoids juggling two providers/keys and keeps latency low end-to-end.
- **Extraction by LLM, scoring by math:** match percentages come from calibrated cosine similarity + exact-match rules (claimed with evidence = 100%, mentioned in a project = 90%, keyword only = 85%), not from asking an LLM "how good a fit is this?". That makes scores reproducible and testable.
- **Evidence-backed scores:** every skill score keeps the resume line it matched, shown on hover, so a score is never a black box.
- **Closed feedback loop:** practice scores are keyed to the same skill objects as the resume match, which enables "claimed but not shown" detection.
- **Session-state only, by design:** no database in v1 — keeps the app simple to run locally and deploy. A natural next step (see below) is persisting practice history.
## Project Structure

```
interview-copilot/
├── app.py                          # landing page / navigation
├── pages/
│   ├── 1_Profile_and_Match.py      # resume + JD -> profile, skill bars, gap explanation
│   ├── 2_Skill_Gap_Plan.py         # gaps -> learning plan
│   ├── 3_Interview_Questions.py    # gap-targeted, skill-tagged questions
│   ├── 4_Practice_Mode.py          # scored practice, feeds skill scores
│   └── 5_Live_Assist.py
├── core/
│   ├── schemas.py                  # CandidateProfile, JobProfile, SkillScore, MatchResult
│   ├── groq_client.py              # chat + transcription wrapper
│   ├── resume_parser.py            # PDF -> text
│   ├── profile_extractor.py        # resume text -> CandidateProfile
│   ├── jd_parser.py                # JD text -> JobProfile
│   ├── embeddings.py               # fastembed (+ lexical fallback)
│   ├── matcher.py                  # deterministic per-skill + responsibility scoring
│   ├── gap_planner.py              # gaps -> learning plan
│   ├── question_gen.py             # resume+JD+gaps -> questions (JSON mode)
│   ├── evaluator.py                # LLM-as-judge answer scoring
│   ├── live_assist.py              # real-time cue generation
│   └── state.py                    # shared session-state helpers
├── eval/
│   ├── labeled_pairs.json          # hand-labeled resume/skill match scores
│   └── run_eval.py                 # MAE, Spearman, gap P/R/F1 + threshold calibration
├── requirements.txt
└── .streamlit/secrets.toml         # local only, gitignored
```

## Evaluating the matcher

`eval/labeled_pairs.json` holds resumes with a hand-assigned 0–100 score for each skill. The three included pairs are **examples**: add 10–20 real ones before quoting numbers.

```bash
python -m eval.run_eval              # MAE, Spearman rank correlation, gap precision/recall/F1
python -m eval.run_eval --calibrate  # grid-search the cosine -> % thresholds in core/matcher.py
```

## Run it locally
 
```bash
git clone https://github.com/<your-username>/interview-copilot.git
cd interview-copilot
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
```
 
Create `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "gsk_your_key_here"
```
(free key: https://console.groq.com/keys)
 
```bash
streamlit run app.py
```
 
## Roadmap
 
- [ ] Persist profiles, matches and practice history to SQLite instead of session state
- [ ] Grow the labeled eval set to 20+ pairs and report held-out metrics
- [ ] Compare several JDs side-by-side ("which role am I closest to?")
- [ ] Export a PDF prep sheet (questions + model answers) after Resume + JD Analysis
- [ ] Multi-model comparison for answer scoring (reuse patterns from my [LLM Benchmarking harness](https://github.com/Dakshina-Nair/LLM-Benchmarking))
- [ ] User accounts for tracking progress across sessions
## Author
 
**Dakshina Nair** — [GitHub](https://github.com/Dakshina-Nair) · [LinkedIn](#)
 

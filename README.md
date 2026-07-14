
# AI Interview Copilot
 
An AI-powered interview preparation tool that generates tailored questions from your resume and a job description, scores your practice answers like a real interviewer would, and gives real-time cue-card assistance during live calls.
 
** Live demo:** [Live Link](https://interview-copilot-4keka9wmap96eadzdsyxy2.streamlit.app/)
 
---
 
## Why I built this
 
Generic interview prep ("tell me about yourself") doesn't map to a specific role or a specific candidate's actual background. This tool closes that gap: every question and every piece of feedback is grounded in the candidate's real resume and the actual job description, not a static question bank.
 
## Features
 
###  Resume + JD Analysis
Upload a resume (PDF) and paste a job description. The app generates 5–20 interview questions spanning Behavioral, Technical, Project-Specific, System Design, and Resume-Gap categories — each with a model answer built from the candidate's real projects and the role's stated requirements.
 
###  Practice Mode
Answer any generated (or fallback) question by typing or speaking. Speech is transcribed automatically. An LLM-as-judge scores the answer across four dimensions — relevance, structure (STAR method), specificity, communication — visualized on a radar chart, with concrete strengths, improvements, and a tightened rewrite. Score history is tracked across attempts on a progress chart.
 
###  Live Assist
Record a live interviewer question during an actual call. Get instant, short cue-card bullets (never a full scripted answer) personalized to the candidate's resume — a real-time memory jog, not a teleprompter.
 
## Tech Stack
 
| Layer | Choice | Why |
|---|---|---|
| UI | Streamlit (multi-page) | Fast to build, matches rest of my portfolio |
| LLM reasoning | Groq — `llama-3.3-70b-versatile` | Free tier, low latency, forced JSON mode for reliable structured output |
| Speech-to-text | Groq — `whisper-large-v3-turbo` | Same API/key as the LLM calls — no second provider to manage |
| PDF parsing | `pypdf` | Lightweight resume text extraction |
| Audio capture | `streamlit-mic-recorder` | In-browser mic recording, no extra backend needed |
| Charts | `plotly` | Radar chart for score breakdown, line chart for progress |
 
## Architecture
 
```
Resume PDF ──┐
             ├─► question_gen.py ──► Groq LLM (JSON mode) ──► tailored questions + model answers
Job Desc ────┘
 
User answer (text/audio) ──► [Whisper transcription if audio] ──► evaluator.py ──► Groq LLM (JSON mode) ──► scored feedback
 
Live audio chunk ──► Whisper transcription ──► live_assist.py ──► Groq LLM ──► cue bullets
```
 
All three flows funnel through a single `core/groq_client.py` wrapper — one place that owns the API key, model names, and JSON-mode handling, so every feature stays consistent and easy to swap models later.
 
## Engineering notes (things I'd highlight in an interview)
 
- **Structured output reliability:** both question generation and answer evaluation force `response_format: json_object` on the Groq call and defensively `json.loads()` with a fallback, instead of trusting free-text LLM output to parse cleanly — the same lesson I hit building an LLM benchmarking harness, where unparsed scores silently broke downstream aggregation.
- **Single API surface:** using Groq for both chat completions and Whisper transcription avoids juggling two providers/keys and keeps latency low end-to-end.
- **Session-state only, by design:** no database in v1 — keeps the app simple to run locally and deploy. A natural next step (see below) is persisting practice history.
## Project Structure
 
```
interview-copilot/
├── app.py                        # landing page / navigation
├── pages/
│   ├── 1_Resume_JD_Analysis.py
│   ├── 2_Practice_Mode.py
│   └── 3_Live_Assist.py
├── core/
│   ├── groq_client.py            # chat + transcription wrapper
│   ├── resume_parser.py          # PDF -> text
│   ├── question_gen.py           # resume+JD -> questions & model answers (JSON mode)
│   ├── evaluator.py              # LLM-as-judge scoring for practice answers
│   └── live_assist.py            # real-time cue generation
├── requirements.txt
└── .streamlit/secrets.toml       # local only, gitignored
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
 
- [ ] Persist practice history to SQLite instead of session state
- [ ] Export a PDF prep sheet (questions + model answers) after Resume + JD Analysis
- [ ] Multi-model comparison for answer scoring (reuse patterns from my [LLM Benchmarking harness](https://github.com/Dakshina-Nair/LLM-Benchmarking))
- [ ] User accounts for tracking progress across sessions
## Author
 
**Dakshina Nair** — [GitHub](https://github.com/Dakshina-Nair) · [LinkedIn](#)
 

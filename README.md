# AI Interview Copilot

Resume-aware interview prep tool. Three modes in one Streamlit app:

1. **Resume + JD Analysis** — upload a resume PDF + paste a job description, get a
   tailored set of likely interview questions (behavioral, technical, project-specific,
   system design, resume-gap) each with a model answer grounded in your actual background.
2. **Practice Mode** — answer questions by typing or speaking (mic recording, transcribed
   via Whisper). Get LLM-as-judge scoring across relevance, structure (STAR), specificity,
   and communication, plus a radar chart, a tightened rewrite of your answer, and a
   progress-over-attempts line chart.
3. **Live Assist** — record a live interviewer question, get instant glance-able cue-card
   bullets (not a scripted answer) personalized to your resume, for use during an actual call.

## Stack

- Streamlit (UI, multi-page)
- Groq API — `llama-3.3-70b-versatile` for reasoning/scoring, `whisper-large-v3-turbo`
  for speech-to-text (one API key covers both)
- `pypdf` for resume parsing, `streamlit-mic-recorder` for in-browser audio capture,
  `plotly` for charts

## Setup (VS Code)

```bash
git clone <your-repo-url> interview-copilot
cd interview-copilot
python -m venv .venv
# Windows Git Bash:
source .venv/Scripts/activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Get a free Groq API key at https://console.groq.com/keys and put it in `.env`:

```
GROQ_API_KEY=gsk_xxx...
```

Run it:

```bash
streamlit run app.py
```

Open the VS Code integrated terminal, run the command above, and Streamlit will open
the app in your browser at `localhost:8501`.

## Project layout

```
interview-copilot/
├── app.py                        # landing page / nav
├── pages/
│   ├── 1_Resume_JD_Analysis.py
│   ├── 2_Practice_Mode.py
│   └── 3_Live_Assist.py
├── core/
│   ├── groq_client.py            # chat + transcription wrapper
│   ├── resume_parser.py          # PDF -> text
│   ├── question_gen.py           # resume+JD -> questions & model answers (JSON mode)
│   ├── evaluator.py               # LLM-as-judge scoring for practice answers
│   └── live_assist.py            # real-time cue generation
├── requirements.txt
├── .env.example
└── .gitignore
```

## Notes / possible extensions

- Session state only — nothing persists across restarts. Adding SQLite for score
  history (you've already done this pattern in the LLM benchmarking harness) is a
  natural next step.
- `question_gen.py` and `evaluator.py` both force `json_mode=True` on Groq's chat
  endpoint so responses parse reliably — same resilient-parsing lesson from the
  `load_run()` bug you hit in the benchmarking project.
- Mic recording needs a browser mic permission grant the first time.

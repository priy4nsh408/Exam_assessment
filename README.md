# MechAssess — AI-Powered Closed-Loop Assessment System

**Team QE29 · RV College of Engineering · Interdisciplinary Project (Semester 6)**

| Member | Program | USN |
|---|---|---|
| Kushal Srivastava | CD | 1RV23CD026 |
| Priyansh Abhishek Poddar | AI | 1RV23AI076 |
| Taran Nithin Rao | AS | 1RV23AS060 |
| D S Sarayu Shree | AS | 1RV23AS012 |

**Guide:** Dr. Vijayalakshmi M N, Associate Professor, AI & ML Dept.

---

## What This Is

Students write exams on paper. The handwritten scripts are scanned and uploaded as PDFs. Faculty uploads the answer scheme, rubrics and marks. The AI evaluates every answer against the marking scheme and produces marks **with explanations** — question by question — while faculty can review and override anything. The goal: drastically reduce evaluation workload without losing quality.

### The evaluation engine (rebuilt — `evaluation/engine/`)

**Fully local — no cloud API, no Tesseract OCR engine.** Handwriting is read by a local Ollama vision model (`llava` by default); typed PDFs are read directly (no AI needed for that part, since the text is already embedded in the file).

| Stage | What happens |
|---|---|
| **1. Reading** | Blank pages auto-detected and skipped (never penalised). Typed PDFs read instantly from the embedded text layer. Handwriting, equations, diagrams and tables are read by your local **Ollama vision model** — one call reads everything on the page. |
| **2. Question detection** | Understands `Q1`, `Q.1`, `Question 1`, `Ans 1`, `1.` and handwritten variations. Stray numbers (marks tables, page numbers) are filtered out. |
| **3. Segmentation** | The script is split into individual answers, each carrying its text, page images, math expressions, and diagram references. |
| **4. Semantic matching** | Answers are matched to the answer scheme **semantically, not positionally** — students can answer Q5, then Q1, then Q8. Un-numbered answers are matched by meaning using local embeddings. |
| **5. Rubric evaluation** | Question type auto-detected (theory / numerical / diagram / derivation / flowchart / graph / mixed). Each type has its own examiner logic: numericals are graded step-wise (formula → substitution → calculation → answer → units), theory by concepts not exact words, diagrams by components and labels not pixels. Partial marks everywhere. |
| **6. Confidence** | A confidence score is attached to every answer for your reference — it flags anything worth a second look, but **never withholds or zeroes out marks**. The answer scheme is always the final word on scoring. |
| **7. Faculty override** | Approve / reject / adjust marks / rewrite feedback per question. Every override is logged in an audit trail and totals recomputed. |
| **8. Reports** | Student report (question-wise marks + feedback + strengths/weaknesses), faculty report (review queue, common mistakes, most-missed concepts), class analytics (average, distribution, question difficulty). |

### Fairness rules (built into every grading prompt)
- Never exact string matching — synonyms and equivalent definitions accepted
- Alternate methods accepted if mathematically correct
- Method marks awarded even when the final answer is wrong
- No deductions that aren't grounded in the rubric (no hallucinated mistakes)

---

## ❓ Do I need an API key?

**No — never.** This app is designed to run entirely on your own machine via **Ollama**, with no cloud account, no API key, and no usage limits.

### One-time setup
```powershell
# 1. Install Ollama: https://ollama.ai
# 2. Pull the vision model (one-time download, then works fully offline):
ollama pull llava
# 3. Make sure Ollama is running, then start/restart the backend
```
The engine automatically detects a running Ollama with `llava` pulled and uses it — no config needed. If your machine can run a bigger model, set `OLLAMA_VISION_MODEL=llama3.2-vision` in a `.env` file at the project root for stronger accuracy.

### Checking what's active
Click the small **AI reading** status pill (top-right of the Evaluate Scripts page) — it makes a real test call to Ollama and reports the actual result, so you always know whether it's working.

### If Ollama isn't set up yet
Use the **Paste Answers** tab — type or paste what the student wrote and it grades against the scheme instantly. No reading step involved at all, so it always works regardless of Ollama's status. For demos, the seeded results (`POST /api/eval/seed-demo`) work regardless too.

---

## Setup (Simple Steps)

### First time only

```powershell
cd C:\Users\sriva\OneDrive\Desktop\IDP6SEMEL

# 1. Allow scripts (once per machine)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 2. Python packages
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# 3. Frontend packages
cd frontend
npm install
cd ..

# 4. Install Ollama and pull the vision model — see "Do I need an API key?" above
```

### Every time you start

**Terminal 1 — Backend**
```powershell
cd C:\Users\sriva\OneDrive\Desktop\IDP6SEMEL
git pull origin claude/practical-goldberg-12yy6e
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend** (new terminal)
```powershell
cd C:\Users\sriva\OneDrive\Desktop\IDP6SEMEL\frontend
npm run dev
```

Open **http://localhost:5173**

---

## How To Use (Faculty Workflow)

**Step 1 — Create the exam / upload answer scheme**
Go to **Answer Schemes**, upload the answer scheme PDF (subject, questions, expected answers and marks are extracted automatically). Or create a full exam with rubrics via `POST /api/eval/exams` (subject, semester, exam name, max marks, per-question rubric, numerical/diagram marking instructions).

**Step 2 — Upload student scripts**
Go to **Evaluate Scripts**, upload the handwritten PDF, pick the scheme, click **Evaluate**. Multiple pages, blank pages, rough work, shuffled question order — all handled automatically.

**Step 3 — Review**
Every answer shows: what the student wrote, awarded marks, rubric breakdown, why marks were given, what was missing, and a confidence score. Low-confidence answers are flagged for a second look, but marks are never withheld — the scheme is always the final word. Use **Faculty Override** to adjust — every change is logged.

**Step 4 — Reports**
**Student Results** shows all evaluated scripts. Class analytics and faculty reports are available at `/api/eval/reports/class` and `/api/eval/reports/faculty`.

---

## Tech Stack

- **Backend:** FastAPI + SQLite (`questions.db`, `overrides.db`, `training_meta.db`, `eval_results.db`)
- **Evaluation engine:** `evaluation/engine/` — modular pipeline (read → detect → segment → match → grade → confidence → reports)
- **Handwriting reading + grading:** local Ollama vision model (`llava` by default) — no cloud, no API key
- **Typed PDFs:** PyMuPDF reads the embedded text layer directly (instant, no AI needed)
- **Text-only grading fallback:** local Ollama text model (`mistral` by default), with a deterministic keyword+semantic grader if Ollama isn't reachable
- **Embeddings:** sentence-transformers `all-MiniLM-L6-v2` (local) for answer↔scheme semantic matching
- **Question generation:** LangGraph 11-agent RAG pipeline + ChromaDB
- **Frontend:** React 18 + TypeScript + Vite + Tailwind

Full model comparison and recommendations per stage: see **[MODELS.md](MODELS.md)**.

## Project Structure

```
Exam_assessment/
├── backend/
│   ├── main.py              # FastAPI app — core endpoints
│   ├── eval_api.py          # Evaluation v2: exams, overrides, reports
│   └── requirements.txt
├── evaluation/
│   ├── engine/              # ★ the evaluation engine (Ollama-only)
│   │   ├── ocr.py           #   blank detection + PyMuPDF typed-text reading
│   │   ├── vision_eval.py   #   Ollama vision: reads + grades handwriting
│   │   ├── detect.py        #   question-number + type detection
│   │   ├── segment.py       #   segmentation + semantic scheme matching
│   │   ├── evaluate.py      #   rubric-based grading per question type
│   │   ├── confidence.py    #   confidence scoring + review flagging
│   │   ├── reports.py       #   student / faculty / class reports
│   │   ├── llm.py           #   local Ollama text-grading client
│   │   ├── embeddings.py    #   MiniLM similarity
│   │   └── pipeline.py      #   orchestrator
│   ├── scheme_parser.py     # answer scheme PDF → structured Q&A
│   └── script_pipeline.py   # compatibility adapter → engine
├── generation/              # LangGraph question generation
├── frontend/src/pages/      # React pages
└── data/                    # SQLite DBs + uploads (not committed)
```

---

## API Reference (evaluation)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/eval/exams` | Create exam (scheme, rubrics, marking instructions) |
| `GET` | `/api/eval/exams` | List exams |
| `POST` | `/api/eval/exams/{id}/evaluate` | Upload script PDF → full AI report |
| `POST` | `/api/eval/script` | Evaluate script against an uploaded answer scheme |
| `POST` | `/api/eval/script/batch` | Batch evaluate (multiple PDFs / ZIP) |
| `GET` | `/api/eval/results` | List saved results |
| `GET` | `/api/eval/results/{id}` | Full report for one result |
| `POST` | `/api/eval/results/{id}/override` | Faculty override (approve/reject/adjust/rewrite) — logged |
| `GET` | `/api/eval/results/{id}/overrides` | Override audit trail |
| `GET` | `/api/eval/reports/faculty` | Review queue, common mistakes, missed concepts |
| `GET` | `/api/eval/reports/class` | Class average, distribution, question difficulty |
| `GET` | `/api/eval/validate/kappa` | Cohen's Kappa (AI vs faculty agreement, target κ ≥ 0.75) |
| `GET` | `/api/health/deps` | Whether the local Ollama vision model is ready right now |
| `GET` | `/api/eval/selftest` | Makes a real test call to Ollama and reports the actual result |
| `POST` | `/api/eval/script/text` | Grade pasted/typed answers directly — no reading step, always works |

---

## Known Limitations

- **Handwriting reading requires Ollama.** Without it running (and `llava` pulled), handwritten scripts can't be read — use **Paste Answers** instead, or set up Ollama (see above).
- Diagram grading is concept-based (from the vision model's description), so it always flags for faculty visual confirmation.
- Grading without Ollama reachable falls back to keyword + semantic similarity for text answers — clearly labelled `keyword_semantic` in the report.
- Vision models on CPU-only machines can take 30–90+ seconds per script; a GPU speeds this up significantly.

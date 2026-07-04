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

| Stage | What happens |
|---|---|
| **1. OCR** | Blank pages auto-detected and skipped (never penalised). Typed PDFs read instantly. Handwriting read by a cloud vision model (Gemini/GPT/Claude) if an API key is set, otherwise Tesseract. Diagrams, graphs and tables are captured as `[DIAGRAM: ...]` descriptions. OCR confidence stored per page. |
| **2. Question detection** | Understands `Q1`, `Q.1`, `Question 1`, `Ans 1`, `1.` and handwritten variations. Stray numbers (marks tables, page numbers) are filtered out. |
| **3. Segmentation** | The script is split into individual answers, each carrying its text, page images, math expressions, diagram references and OCR confidence. |
| **4. Semantic matching** | Answers are matched to the answer scheme **semantically, not positionally** — students can answer Q5, then Q1, then Q8. Un-numbered answers are matched by meaning using embeddings. |
| **5. Rubric evaluation** | Question type auto-detected (theory / numerical / diagram / derivation / flowchart / graph / mixed). Each type has its own examiner logic: numericals are graded step-wise (formula → substitution → calculation → answer → units), theory by concepts not exact words, diagrams by components and labels not pixels. Partial marks everywhere. |
| **6. Confidence engine** | Weighted score from OCR quality + grader certainty + rubric coverage + match certainty + completeness. **Below 80% → sent to faculty review automatically. Illegible handwriting → no marks auto-assigned at all.** |
| **7. Faculty override** | Approve / reject / adjust marks / rewrite feedback per question. Every override is logged in an audit trail and totals recomputed. |
| **8. Reports** | Student report (question-wise marks + feedback + strengths/weaknesses), faculty report (review queue, common mistakes, most-missed concepts), class analytics (average, distribution, question difficulty). |

### Fairness rules (built into every grading prompt)
- Never exact string matching — synonyms and equivalent definitions accepted
- Alternate methods accepted if mathematically correct
- Method marks awarded even when the final answer is wrong
- No deductions that aren't grounded in the rubric (no hallucinated mistakes)

---

## ❓ Do I need an API key?

**No — it works without one.** But here is the honest difference:

| | Without any API key (free, offline) | With an API key |
|---|---|---|
| Typed / digital PDFs | ✅ Perfect | ✅ Perfect |
| **Handwritten scripts** | ⚠️ Weak — Tesseract is a print-OCR engine, it struggles with handwriting | ✅ Excellent — cloud vision models read handwriting, equations and diagrams |
| Grading quality | ⚠️ Approximate — keyword + semantic similarity scoring (clearly labelled, flagged for faculty review) | ✅ Real examiner-style rubric grading with explanations |
| Ollama installed locally? | Adds proper LLM grading (Mistral) but still weak handwriting OCR | Not needed |

**Recommendation:** get a **free Gemini API key** (no credit card needed) from https://aistudio.google.com/apikey — the free tier is enough for this project. Then before starting the backend:

```powershell
# Windows PowerShell (once — persists across restarts)
setx GEMINI_API_KEY "your-key-here"
# then close and reopen the terminal
```

That single key upgrades **both** handwriting OCR **and** grading quality. No code changes needed — the engine detects it automatically.

If you truly can't use any key: the system still runs end-to-end, results are just approximate for handwriting and everything low-confidence goes to the faculty review queue. For demos, use the seeded results (`POST /api/eval/seed-demo`).

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

# 4. (Optional, for offline handwriting OCR) install Tesseract:
#    https://github.com/UB-Mannheim/tesseract/wiki  → run installer, keep default path

# 5. (Optional but recommended) free Gemini key — see section above
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
Every answer shows: the OCR text, awarded marks, rubric breakdown, why marks were given, what was missing, and a confidence score. Anything under 80% confidence lands in the review queue. Use **Faculty Override** to adjust — every change is logged.

**Step 4 — Reports**
**Student Results** shows all evaluated scripts. Class analytics and faculty reports are available at `/api/eval/reports/class` and `/api/eval/reports/faculty`.

---

## Tech Stack

- **Backend:** FastAPI + SQLite (`questions.db`, `overrides.db`, `training_meta.db`, `eval_results.db`)
- **Evaluation engine:** `evaluation/engine/` — modular pipeline (OCR → detect → segment → match → grade → confidence → reports)
- **OCR:** PyMuPDF (typed PDFs, page rendering) → cloud VLM (handwriting, optional) → Tesseract (offline fallback)
- **Grading LLM ladder:** Claude → OpenAI → Gemini → local Ollama Mistral (first available wins, hard timeouts — nothing ever hangs)
- **Embeddings:** sentence-transformers `all-MiniLM-L6-v2` (local, free) for answer↔scheme semantic matching
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
│   ├── engine/              # ★ the evaluation engine
│   │   ├── ocr.py           #   blank detection, PyMuPDF, VLM, Tesseract
│   │   ├── detect.py        #   question-number + type detection
│   │   ├── segment.py       #   segmentation + semantic scheme matching
│   │   ├── evaluate.py      #   rubric-based grading per question type
│   │   ├── confidence.py    #   confidence engine + review routing
│   │   ├── reports.py       #   student / faculty / class reports
│   │   ├── llm.py           #   provider ladder with timeouts
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
| `GET` | `/api/health/deps` | Which OCR/LLM capabilities are available right now |

---

## Known Limitations

- **Handwriting OCR without an API key is approximate.** Tesseract was built for print. Scan at ≥300 DPI, write clearly, or set a (free) Gemini key.
- Diagram grading is concept-based (from the OCR/VLM description), so it always flags for faculty visual confirmation.
- Grading without any LLM (no key + no Ollama) falls back to keyword + semantic similarity — clearly labelled `keyword_semantic` in the report and routed to faculty review.

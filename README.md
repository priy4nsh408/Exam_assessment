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

MechAssess is a closed-loop AI assessment platform for Mechanical Engineering education. It covers the complete assessment lifecycle — from AI-generated exam papers to automated answer-script grading with human-in-the-loop faculty override.

### Core capabilities

| Module | What it does |
|---|---|
| **Question Generation** | 11-agent LangGraph RAG pipeline generates syllabus-aligned questions tagged with Bloom level, CO/PO, difficulty, and marks. SHA-256 deduplication prevents repeats. |
| **Answer Scheme Upload** | Upload an answer scheme PDF — system OCRs it and extracts subject, questions, expected answers, and marks per question automatically |
| **Answer Script Evaluation** | Upload student PDF → select answer scheme → OCR → auto-segment by question → auto-classify (theory/numerical/drawing) → AI score → report |
| **Theory Evaluator** | sentence-transformers cosine similarity + ME keyword bank (40% keyword / 60% semantic blend) |
| **Numerical Grader** | Step-level LLM chain-of-thought with 5-category error classification; heuristic fallback works without Ollama |
| **Drawing Evaluator** | OpenCV preprocessing → EasyOCR extracts text labels & dimensions → matches expected parts → deducts for missing; always flags for faculty visual review |
| **CO/PO Analytics** | Course Outcome and Program Outcome attainment charts per batch |
| **Faculty Override** | SQLite-persisted grade overrides survive restarts; Cohen's Kappa tracks AI–faculty agreement (target κ ≥ 0.75) |
| **Batch Evaluation** | Upload multiple student scripts or a ZIP → class summary + per-student drill-down + CSV export |

---

## How Evaluation Works (End-to-End Flow)

```
1. Faculty uploads Answer Scheme PDF  →  Answer Schemes page
        │
        │  OCR + parse
        ▼
   Extracted: subject · Q1 question + expected answer + marks
              Q2 question + expected answer + marks  ...
        │
        │  stored in SQLite
        ▼

2. Faculty uploads Student Answer Script PDF  →  Evaluate Scripts page
        │  (selects the answer scheme uploaded above)
        │
        ▼
   EasyOCR  ──────────────────  per-page confidence score
        │
        ▼
   Segment by Q-number  ──────  regex: "Q1", "1.", "Answer 1", etc.
        │
        ▼
   Classify each answer automatically
    ├─ theory    →  sentence-transformers (keyword + semantic vs. expected answer)
    ├─ numerical →  LLM step-grader / heuristic fallback
    └─ drawing   →  OCR label match + faculty review flag
        │
        ▼
   Aggregate Report
   total_score / max_total / percentage / per-question detail
        │
        ▼
   Faculty Override  ──  persisted in overrides.db
        │
        ▼
   Cohen's Kappa  ─────  κ ≥ 0.75 target
```

### What the answer scheme provides
When a scheme is selected during evaluation, the system automatically uses:
- **Subject** — for selecting the right keyword bank in theory grading
- **Expected answer per question** — compared against student's text for scoring accuracy
- **Marks per question** — determines score out of X for each answer

Nothing needs to be typed manually during evaluation.

---

## Tech Stack

### Backend
- **FastAPI** — REST API server
- **SQLite** — four databases: `questions.db`, `overrides.db`, `training_meta.db`, `eval_results.db`
- **LangGraph + LangChain** — 11-agent question generation pipeline
- **ChromaDB** — vector store for RAG
- **sentence-transformers** (`all-MiniLM-L6-v2`) — semantic similarity for theory grading
- **PyMuPDF** (`fitz`) — direct text extraction from typed/digital PDFs (no poppler needed)
- **EasyOCR** — deep-learning OCR for handwritten answer scripts, drawing labels, and scheme parsing
- **OpenCV** (`opencv-python-headless`) — image preprocessing (adaptive threshold) before OCR
- **pdf2image + poppler** — PDF → image conversion for scanned/handwritten scripts (optional; PyMuPDF used first)
- **Ollama** (optional) — local LLM for numerical step grading; heuristic fallback used if unavailable

### Frontend
- **React 18 + TypeScript + Vite**
- **Tailwind CSS**
- **lucide-react** — icons
- **react-router-dom** — client-side routing

---

## Project Structure

```
Exam_assessment/
├── backend/
│   ├── main.py              # FastAPI app — all REST endpoints
│   └── requirements.txt
├── evaluation/
│   ├── scheme_parser.py     # OCR + parse answer scheme PDFs → structured Q&A
│   ├── ocr_engine.py        # EasyOCR + pdf2image pipeline
│   ├── script_pipeline.py   # PDF → OCR → segment → classify → evaluate → report
│   ├── theory_evaluator.py  # sentence-transformers keyword+semantic grader
│   ├── numerical_grader.py  # LLM step-level grader with heuristic fallback
│   └── drawing_evaluator.py # OCR-based label/dimension checker
├── generation/
│   └── pipeline.py          # LangGraph 11-agent question generation
├── frontend/
│   └── src/
│       ├── App.tsx
│       └── pages/
│           ├── Dashboard.tsx
│           ├── QuestionGenerator.tsx
│           ├── QuestionBank.tsx
│           ├── ExamPapers.tsx
│           ├── DataSource.tsx
│           ├── AnswerScriptEvaluator.tsx  # single hub: upload script + select scheme
│           ├── TrainingEngine.tsx         # upload + preview answer schemes
│           ├── ValidationMetrics.tsx      # Cohen's Kappa
│           ├── COPOAnalytics.tsx
│           ├── Students.tsx
│           └── FacultyOverride.tsx
├── data/
│   ├── questions.db
│   ├── overrides.db
│   ├── training_meta.db     # scheme metadata + parsed questions JSON
│   ├── eval_results.db      # all evaluation results (persists across restarts)
│   └── training_refs/       # uploaded scheme PDFs
└── ingestion/               # syllabus/PYQ ingestion scripts
```

---

## Setup

### 1. Python environment

```bash
cd Exam_assessment
python -m venv venv

# Windows (PowerShell)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r backend/requirements.txt
```

Key Python packages:
- `pymupdf>=1.23.0` — direct PDF text extraction, **no system dependencies**
- `easyocr>=1.7.1` — OCR engine for handwritten scripts (downloads ~100 MB model on first run)
- `pdf2image>=1.17.0` — fallback for scanned PDFs (requires poppler — see below)
- `opencv-python-headless==4.10.0.84` — image preprocessing
- `sentence-transformers==3.2.1` — theory semantic scoring
- `fastapi==0.115.0` + `uvicorn[standard]==0.31.0`

### 2. (Optional) Poppler — only needed for scanned/handwritten PDFs

Answer schemes are typed PDFs — PyMuPDF handles them with no extra install.
Poppler is only needed if student scripts are scanned PDFs (not digital).

```bash
# Ubuntu / Debian
sudo apt-get install -y poppler-utils

# macOS
brew install poppler

# Windows: download from https://github.com/oschwartz10612/poppler-windows/releases
# Unzip and add the Library\bin folder to your system PATH, then restart VS Code
```

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. (Optional) Ollama for numerical grading LLM feedback

```bash
# Install from https://ollama.ai
ollama pull mistral
```

If Ollama is not running, numerical grading uses a heuristic fallback that still works.

---

## Running

```bash
# Terminal 1 — backend
cd backend
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
# source ../venv/bin/activate

uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:5173`

---

## How to Evaluate Answer Scripts (Step-by-Step)

### Step 1 — Upload answer scheme

Go to **Answer Schemes** in the sidebar.

- Add an optional description (e.g. "Aerospace Structures VTU Dec 2023")
- Upload your answer scheme PDF
- The system OCRs it and extracts each question, expected answer, and marks automatically
- A preview shows every parsed question — verify it looks correct

**Tips for best parsing:**
- Number questions clearly: `Q1.` or `1.` or `Question 1` at the start of a line
- Write marks as `[10M]` or `(5 marks)` near each question
- Write expected answers immediately after the question or after `Ans:` / `Answer:`
- Typed/digital PDFs parse better than scanned ones

### Step 2 — Evaluate student scripts

Go to **Evaluate Scripts** in the sidebar.

- Upload the student's handwritten answer PDF
- Select your answer scheme from the dropdown (subject + marks loaded automatically)
- Optionally enter student name and USN
- Click **Evaluate Script**

The system automatically:
- OCRs the handwriting (EasyOCR for scanned; PyMuPDF for typed)
- Applies an OCR confidence penalty — low-confidence text scores lower to avoid inflation
- Segments answers by question number
- Classifies each as theory, numerical, or drawing
- Scores against the expected answers from your scheme
- Saves the result permanently — visible in **Student Results** after any refresh

### Step 3 — Faculty review and override

- Drawing questions are always flagged for visual review
- Questions without a reference answer are flagged and given 0 pending faculty review
- Low OCR confidence pages are highlighted with a warning
- Use **Faculty Override** to adjust any score; saved permanently in SQLite

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/health/deps` | OCR dependency status |
| `POST` | `/api/training/upload` | Upload and parse an answer scheme PDF |
| `GET` | `/api/training/references` | List uploaded schemes with parsed questions |
| `DELETE` | `/api/training/references/{id}` | Delete a scheme |
| `POST` | `/api/eval/script` | Evaluate single answer script (saves to eval_results.db) |
| `POST` | `/api/eval/script/batch` | Evaluate multiple scripts or ZIP (saves each to eval_results.db) |
| `GET` | `/api/eval/results` | List all saved evaluation results |
| `GET` | `/api/eval/results/{id}` | Full report for one evaluation |
| `DELETE` | `/api/eval/results/{id}` | Delete an evaluation result |
| `POST` | `/api/submissions/{id}/override` | Submit faculty grade override (SQLite persistent) |
| `GET` | `/api/submissions/overrides` | List all grade overrides (audit trail) |
| `GET` | `/api/eval/validate/kappa` | Cohen's Kappa AI vs faculty agreement report |
| `POST` | `/api/questions/generate` | Generate questions via LangGraph pipeline |
| `GET` | `/api/questions` | List all questions in the question bank |
| `GET` | `/api/analytics/co` | CO attainment data |
| `GET` | `/api/analytics/co-trend` | CO coverage trend across published exams |
| `GET` | `/api/students/export/csv` | Download student grades CSV |

---

## Feature Status

### Working
- [x] LangGraph 11-agent question generation with RAG
- [x] Question Bank with filters, CO/PO tags, export
- [x] Exam paper generation and management
- [x] Answer scheme upload → OCR (PyMuPDF / EasyOCR) → extract questions/answers/marks
- [x] Answer script OCR pipeline (PDF + image, typed + handwritten)
- [x] OCR confidence penalty — low-quality scans score lower, preventing inflation
- [x] Auto-classification (theory / numerical / drawing) — no manual selection needed
- [x] Theory evaluator (keyword + semantic similarity vs. expected answer)
- [x] Numerical grader with heuristic fallback (no Ollama required)
- [x] Drawing evaluator (OCR label matching + faculty review flag)
- [x] Questions without reference answer flagged for faculty review (score = 0)
- [x] Evaluation results persisted in `eval_results.db` — survive restarts and navigation
- [x] Batch evaluation with class summary — results saved to DB automatically
- [x] Student Results page — real data, search, CSV export, per-question drill-down
- [x] At-risk student flag (below 40%)
- [x] Faculty grade override (SQLite persistent, audit trail)
- [x] Cohen's Kappa validation dashboard
- [x] CO/PO analytics

### Requires Faculty Action (by design)
- [ ] Drawing line-work review — AI checks labels only, not actual shapes
- [ ] Low OCR confidence pages (< 60%) flagged for manual re-check
- [ ] Numerical problems with novel notation may need score override

### Known Limitations
- EasyOCR accuracy on very light pencil or smudged handwriting is ~70–80%. Scan at ≥300 DPI for best results.
- Numerical LLM grading requires Ollama running locally; heuristic fallback gives approximate scores.
- First OCR run downloads ~100 MB model weights (one-time, cached after).
- Answer scheme parsing works best when questions are clearly numbered and answers follow immediately.

---

## Cohen's Kappa Target

| κ range | Interpretation |
|---|---|
| < 0.40 | Poor agreement — retrain needed |
| 0.40–0.60 | Moderate |
| 0.60–0.75 | Substantial |
| **≥ 0.75** | **Target — excellent agreement** |

The `/eval/validate` page shows live κ per question type and triggers a warning if any category falls below threshold.

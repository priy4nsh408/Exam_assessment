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
- **SQLite** — three databases: `questions.db`, `overrides.db`, `training_meta.db`
- **LangGraph + LangChain** — 11-agent question generation pipeline
- **ChromaDB** — vector store for RAG
- **sentence-transformers** (`all-MiniLM-L6-v2`) — semantic similarity for theory grading
- **EasyOCR** — deep-learning OCR for handwritten answer scripts, drawing labels, and scheme parsing
- **OpenCV** (`opencv-python-headless`) — image preprocessing (adaptive threshold) before OCR
- **pdf2image + poppler** — PDF → image conversion for OCR
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
│   └── training_refs/       # uploaded scheme PDFs
└── ingestion/               # syllabus/PYQ ingestion scripts
```

---

## Setup

### 1. System dependency — poppler (for PDF support)

```bash
# Ubuntu / Debian
sudo apt-get install -y poppler-utils

# macOS
brew install poppler

# Windows: download from https://github.com/oschwartz10612/poppler-windows/releases
# unzip and add the bin/ folder to your system PATH
```

### 2. Python environment

```bash
cd Exam_assessment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r backend/requirements.txt
```

Key Python packages:
- `easyocr>=1.7.1` — OCR engine (downloads ~100 MB model on first run)
- `pdf2image>=1.17.0` — requires poppler
- `opencv-python-headless==4.10.0.84` — image preprocessing
- `sentence-transformers==3.2.1` — theory semantic scoring
- `fastapi==0.115.0` + `uvicorn[standard]==0.31.0`

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. (Optional) Ollama for numerical grading

```bash
# Install from https://ollama.ai
ollama pull mistral
```

If Ollama is not running, numerical grading uses a heuristic fallback that still works.

---

## Running

```bash
# Terminal 1 — backend (from repo root)
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:5173`

---

## How to Evaluate Answer Scripts (Step-by-Step)

### Step 1 — Upload answer scheme

Go to **Answer Schemes** in the sidebar.

Upload your answer scheme PDF. The system will:
- OCR the file and extract each question, its expected answer, and marks
- Detect the subject from the document header
- Show you a preview of what was parsed

**Tips for best parsing:**
- Start each question with `Q1.` or `1.` or `Question 1`
- Write marks as `[10M]` or `(5 marks)` near the question
- Write expected answers after the question, or after `Ans:` / `Answer:`

### Step 2 — Evaluate student scripts

Go to **Evaluate Scripts** in the sidebar.

- Upload the student's handwritten answer PDF
- Select your answer scheme from the dropdown
- Click **Evaluate Script**

The system automatically:
- OCRs the handwriting
- Segments answers by question number
- Classifies each as theory, numerical, or drawing
- Scores against the expected answers from your scheme
- Returns a full report with scores, feedback, and confidence

### Step 3 — Faculty review and override

- Drawing questions are always flagged for visual review
- Low OCR confidence pages are highlighted
- Use **Faculty Override** to adjust any score; changes are saved permanently

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/health/deps` | OCR dependency status |
| `POST` | `/api/questions/generate` | Generate questions via LangGraph |
| `GET` | `/api/questions` | List all questions |
| `POST` | `/api/eval/script` | Evaluate single answer script |
| `POST` | `/api/eval/script/batch` | Evaluate multiple scripts or ZIP |
| `POST` | `/api/grades/override` | Submit faculty grade override (SQLite persistent) |
| `GET` | `/api/submissions/overrides` | List all grade overrides |
| `GET` | `/api/eval/validate/kappa` | Cohen's Kappa report |
| `POST` | `/api/training/upload` | Upload and parse an answer scheme PDF |
| `GET` | `/api/training/references` | List uploaded schemes with parsed questions |
| `DELETE` | `/api/training/references/{id}` | Delete a scheme |
| `GET` | `/api/students` | Student list with CO summaries |
| `GET` | `/api/students/export/csv` | Download student CSV |
| `GET` | `/api/co-po/analytics` | CO/PO attainment data |

---

## Feature Status

### Working
- [x] LangGraph 11-agent question generation with RAG
- [x] Question Bank with filters, CO/PO tags, export
- [x] Exam paper generation and management
- [x] Answer scheme upload → OCR → extract questions/answers/marks
- [x] Answer script OCR pipeline (PDF + image)
- [x] Auto-classification (theory / numerical / drawing)
- [x] Theory evaluator (keyword + semantic similarity vs. expected answer)
- [x] Numerical grader with heuristic fallback
- [x] Drawing evaluator (OCR label matching)
- [x] Batch evaluation with class summary + CSV export
- [x] Faculty grade override (SQLite persistent)
- [x] Cohen's Kappa validation dashboard
- [x] CO/PO analytics
- [x] Student drill-down with at-risk flagging
- [x] OCR dependency guard (shows install instructions if missing)

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

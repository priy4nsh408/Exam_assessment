# MechAssess — AI-Powered Question Generation & Evaluation System

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

MechAssess is a closed-loop AI assessment platform for Mechanical Engineering education. It covers the complete assessment lifecycle:

1. **Question Generation** — 11-agent LangGraph RAG pipeline generates syllabus-aligned questions with Bloom level, CO/PO tags, SHA-256 deduplication, and SQLite persistence
2. **Unified Answer Evaluation** — Upload answer scheme PDF + student answer scripts (images or scanned/handwritten PDFs), auto-parses all questions with marks, evaluates each question with per-question score breakdown, keyword analysis, conceptual accuracy, and completeness metrics. Scanned PDFs go through an OCR + semantic-similarity page-mapping pipeline that attributes each page to the right question — including pages that mix the end of one answer with the start of the next — before grading the transcribed text through the same LLM path as typed answers
3. **Exam Paper Export** — Generates the question paper and answer scheme as college-format PDFs matching the department's printed letterhead (crest, course code/date/duration, SL.No/Questions/Marks/BT/CO table, Course Outcome descriptions, Marks Distribution footer), and can re-parse its own exported PDFs back into structured questions for grading
4. **Theory Evaluation** — Two-tier LLM scoring (concept + detail) with ME keyword banks and cosine similarity
5. **Numerical Grading** — Step-level automated grading with 5-category error classification via chain-of-thought LLM
6. **Drawing Evaluation** — OpenCV preprocessing + YOLOv8 detection + LLaVA VLM + IS/BIS compliance engine
7. **Evaluated Answer Scripts** — History of all evaluations with expandable per-question breakdown (full question/feedback text, not truncated), faculty score override with reason tracking, and low OCR confidence warnings
8. **Unified Dashboard** — React + TypeScript frontend with real-time SSE streaming, CO/PO analytics, and human-in-the-loop grade override

---

## Project Structure

```
Exam_assessment/
├── frontend/                    # React + TypeScript + Tailwind CSS dashboard
│   └── src/
│       ├── pages/               # 11 dashboard pages (all wired to real API)
│       ├── components/          # Sidebar, Header, StatCard, BloomBadge
│       ├── types/               # TypeScript entity types
│       └── api/                 # Fetch client
├── backend/
│   ├── main.py                  # FastAPI — 20+ endpoints + SSE streaming
│   ├── exam_pdf.py              # College-format PDF export (ReportLab) — letterhead, question table, CO/marks footer
│   ├── assets/                  # college_logo.png (optional crest embedded in exported PDFs)
│   └── requirements.txt
├── generation/
│   ├── langgraph_pipeline.py    # 11-agent LangGraph pipeline + SQLite + SHA-256
│   └── generator.py             # Legacy single-agent Ollama generator
├── evaluation/
│   ├── unified_evaluator.py     # Unified evaluator: OCR (LLaVA), LLM grading, heuristic scoring
│   ├── theory_evaluator.py      # Cosine similarity + keyword coverage + LLM grader
│   ├── numerical_grader.py      # Step-level grader, 5-category error classifier
│   └── drawing_evaluator.py     # OpenCV + YOLOv8 stub + LLaVA + IS/BIS engine
├── ingestion/                   # PDF/DOCX/PPTX loader with metadata extraction
├── chunking/                    # Text splitter (500-char chunks, 100-char overlap)
├── vector_store/                # ChromaDB client + semantic retriever
├── pyq_processing/              # Previous year question parser
├── tagging/                     # Bloom's taxonomy + CO validation
├── app/                         # Legacy Streamlit UI + CLI (still functional)
├── data/
│   ├── raw/                     # Subject PDFs (BDT, Structural Mechanics, Propulsion, Structures)
│   ├── pyqs/                    # Previous year question papers
│   ├── db/                      # Pre-built ChromaDB vector stores
│   ├── questions.db             # SQLite question bank (auto-created)
│   ├── eval_history.db          # SQLite evaluation history (auto-created)
│   ├── uploads/                 # Student answer scripts & scheme PDFs (auto-created)
│   └── demo_answer.pdf          # Demo student answer script for BDT CIE3 testing
└── requirements.txt             # Python dependencies
```

---

## Running the Project

### React Dashboard (primary interface)

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### FastAPI Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# Runs at http://localhost:8000
# Gracefully falls back to mock data if Ollama is not running
```

### Ollama Models (for full AI functionality)

```bash
ollama pull mistral          # Question generation
ollama pull llava            # Drawing VLM interpretation
ollama pull deepseek-r1      # Numerical step grading (optional)
```

### Environment

Create a `.env` file in the root:
```
OLLAMA_MODEL=mistral
```

### Legacy Streamlit UI

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

---

## Dashboard Pages

All 11 pages are wired to the real FastAPI backend with graceful fallbacks.

| Route | Page | API Used | Description |
|---|---|---|---|
| `/` | Dashboard | `/api/stats` | Stat cards, Bloom distribution, CO attainment bars, activity feed |
| `/generate` | Question Generator | `/api/questions/generate/stream` (SSE) | Live agent pipeline status, configure and generate questions |
| `/questions` | Question Bank | `/api/questions` | Search/filter all SQLite-backed questions |
| `/evaluate` | Answer Evaluator | `/api/eval/unified`, `/api/eval/batch`, `/api/eval/parse-scheme` | Upload scheme PDF + student answers, single/batch mode, per-question breakdown |
| `/evaluated-scripts` | Evaluated Scripts | `/api/eval/history` | Evaluation history with expandable details, faculty override, delete |
| `/exams` | Exam Papers | `/api/exams`, `/api/exams/{id}/export/paper`, `/api/exams/{id}/export/scheme`, `/api/co-descriptions/{subject}` | Exam paper management, college-format PDF export (blank paper + answer scheme), per-subject CO description editor |
| `/data-sources` | Data Sources | `/api/data-sources` | Manage uploaded course materials |
| `/analytics` | CO/PO Analytics | `/api/analytics/co` | Bar chart, radar, trend lines, CO–PO correlation matrix |
| `/students` | Students | `/api/students` | Per-student CO attainment with At-Risk flagging |
| `/override` | Faculty Override | `/api/submissions` + `/api/submissions/{id}/override` | Flagged submission queue, override score + reason |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | System status — LangGraph, Ollama, evaluator availability |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/questions/generate` | Generate questions via LangGraph pipeline |
| GET | `/api/questions/generate/stream` | SSE — streams 9 agent events then final questions |
| GET | `/api/questions` | List questions from SQLite (filters: subject, unit, bloom, type) |
| DELETE | `/api/questions/{id}` | Remove a question from SQLite |
| GET | `/api/students` | Student roster |
| GET | `/api/submissions` | All submissions (filter: status=flagged) |
| POST | `/api/submissions/{id}/grade` | AI-grade a submission |
| POST | `/api/submissions/{id}/override` | Faculty override with score + reason |
| GET | `/api/analytics/co` | CO attainment data with Bloom coverage breakdown |
| GET | `/api/exams` | List exam papers |
| POST | `/api/exams` | Create an exam paper (with letterhead metadata: course code, semester, CIE label, exam date, academic year, department) |
| GET | `/api/exams/{id}/export/paper` | Export a blank college-format question paper PDF (letterhead, SL.No/Questions/Marks/BT/CO table, Marks Distribution footer) |
| GET | `/api/exams/{id}/export/scheme` | Export the answer scheme PDF — same layout with model answer + validation note under each question |
| GET | `/api/co-descriptions/{subject}` | Get a subject's CO1–CO5 descriptions (shown in the exported PDF's Course Outcome footer) |
| POST | `/api/co-descriptions/{subject}` | Save a subject's CO1–CO5 descriptions |
| POST | `/api/eval/unified` | Unified evaluator — auto-detects multi-question schemes, returns per-question breakdown |
| POST | `/api/eval/batch` | Batch evaluate multiple student scripts against parsed scheme questions |
| POST | `/api/eval/parse-scheme` | Parse answer scheme PDF — extracts questions, marks, types, reference answers |
| GET | `/api/eval/history` | Evaluation history with per-question results |
| POST | `/api/eval/history/{id}/override` | Faculty score override with reason |
| DELETE | `/api/eval/history/{id}` | Delete an evaluation record |
| POST | `/api/eval/theory` | Grade a theory answer (keyword + cosine + LLM) |
| POST | `/api/eval/numerical` | Grade a numerical solution step-by-step |
| POST | `/api/eval/drawing` | Evaluate an engineering drawing (file upload) |

---

## Implementation Status

### Module 1 — Question Generation Engine
- [x] ChromaDB vector store with sentence-transformers (all-MiniLM-L6-v2)
- [x] Bloom-Adaptive RAG retrieval with adaptive-k based on cognitive level
- [x] 11-agent LangGraph pipeline (BloomAnalyzer → Scout → Generator → QualityValidator → DifficultyValidator → CorrectnessValidator → PedagogyTagger → SyllabusGuardian → Archivist)
- [x] SHA-256 deduplication — prevents duplicate questions across sessions
- [x] SQLite persistence with full provenance metadata (`data/questions.db`)
- [x] FastAPI SSE streaming — live agent status events to frontend
- [x] Graceful fallback (LangGraph graph → manual agent loop → mock templates)

### Module 2 — Unified Answer Evaluation (End-to-End Grading Pipeline)
- [x] Answer scheme PDF parsing — heuristic parser (primary) + LLM fallback for unstructured docs
- [x] Handles exam formats: `Q1.1`, `1a`, `5`, table-based M/BT/CO marks, inline `[X marks]`, `Total X Marks`
- [x] Dedicated parser for this app's own exported college-format table PDFs (`_parse_rvce_table_scheme`) — round-trips the SL.No/Questions/Marks/BT/CO layout, including splitting out Model Answer/Validation text for the scheme export
- [x] Multi-question evaluation — evaluates student answer against ALL parsed questions, not just one
- [x] Parallel evaluation with ThreadPoolExecutor (up to 6 concurrent) for faster grading
- [x] LLM-based comprehensive grading via Ollama — reads both scheme + student answer together
- [x] 6 evaluation metrics: keyword coverage, conceptual accuracy, completeness, equation check, formula check, final answer check
- [x] Heuristic fallback scoring: keyword coverage (40%) + semantic similarity (60%)
- [x] OCR support via LLaVA vision model for handwritten answer papers (images)
- [x] PDF student answers — auto-extracts text from uploaded PDF answer scripts
- [x] Robust PDF extraction with 3 fallbacks: pypdf → PyMuPDF → PyPDF2
- [x] Scanned/handwritten PDF page-to-question mapping — Tesseract on the left margin, then OCR + sentence-embedding similarity match against each question's text/reference answer (not a direct vision-model judgment call, which testing showed is unreliable for this)
- [x] Boundary-page detection — a page mixing the tail of one answer with the start of the next is split top/bottom and each half matched independently, instead of being forced entirely into one question
- [x] OCR-then-text-grade for scanned pages — transcribes the mapped pages first, then grades the text through the same LLM path as typed answers, rather than asking the vision model to judge relevance and score directly from the raw image
- [x] Request-scoped OCR cache — a page's transcription is computed once and reused between page-mapping and grading instead of being redone
- [x] Per-question score breakdown with total aggregation and batch results display
- [x] Single mode + Batch mode — upload one or multiple student scripts against a scheme
- [x] Evaluated Scripts history page with expandable per-question details (full question/feedback text)
- [x] Faculty score override with reason tracking and low OCR confidence warnings
- [x] Filename sanitization for Windows compatibility
- [x] Startup PDF dependency check with install instructions

### Module 3 — Theory Answer Evaluation Engine (Legacy)
- [x] Frontend UI: upload, results list, keyword found/missing analysis, score breakdown, override form
- [x] Two-tier LLM scoring: concept score (0–5) + detail score (0–5) via Ollama
- [x] ME keyword banks for Thermodynamics, SOM, Fluid Mechanics, Engineering Drawing
- [x] Cosine similarity via sentence-transformers
- [x] `/api/eval/theory` endpoint — fully functional
- [ ] ME rubric dataset (150+ Q&A pairs with keyword annotations — **needs ME team**)
- [ ] Cohen's Kappa validation run against faculty scores

### Module 4 — Numerical Step-Level Grader
- [x] Frontend UI: step-by-step breakdown, 5-category error badges, partial credit display
- [x] LLM chain-of-thought step evaluator via Ollama
- [x] 5-category error classifier: formula / substitution / unit / arithmetic / boundary condition
- [x] Partial credit per step, heuristic fallback when LLM unavailable
- [x] `/api/eval/numerical` endpoint — fully functional
- [ ] ME numerical problem bank (100+ problems with step rubrics — **needs ME team**)
- [ ] Step-level accuracy validation (target ≥ 90%)

### Module 5 — Engineering Drawing Evaluator
- [x] Frontend UI: element detection grid, IS clause violation list, LLaVA JSON panel, upload
- [x] OpenCV preprocessing: CLAHE → Hough-line deskew → adaptive threshold → morphological denoise → 1024×768
- [x] YOLOv8 heuristic stub (quadrant-based element detection until trained weights available)
- [x] LLaVA VLM via Ollama for semantic JSON interpretation
- [x] IS/BIS compliance engine: IS 696:1972 (projection angle, view count), IS 919:1993 (tolerance notation), SP:46:2003 (title block), IS 3073:1967 (surface finish)
- [x] `/api/eval/drawing` endpoint with file upload — fully functional
- [ ] Annotated drawing dataset (100+ drawings — **needs ME team**)
- [ ] YOLOv8 fine-tuning on annotated dataset (use Google Colab T4 GPU)

### Module 6 — Unified Dashboard
- [x] React 18 + TypeScript + Vite + Tailwind CSS + Recharts frontend
- [x] All 11 pages wired to real FastAPI backend with graceful fallbacks
- [x] Answer Evaluator page — single/batch mode, scheme PDF upload, parsed questions preview, per-question score table with full (non-truncated) question/feedback text
- [x] Evaluated Scripts page — evaluation history, expandable per-question breakdown (full question/feedback text) with faculty override modal
- [x] CO/PO analytics: bar chart, radar chart, trend line chart, CO–PO correlation matrix
- [x] Faculty override panel with confidence-based flagging and API-backed submission
- [x] Real-time SSE streaming for question generation with live agent status
- [x] SQLite-backed question bank with search, filter, delete

### Module 7 — Exam Paper Export (College-Format PDF)
- [x] `backend/exam_pdf.py` — ReportLab-based PDF renderer shared by both the paper and scheme exports
- [x] Running letterhead on every page: crest slot (optional `backend/assets/college_logo.png`), college name/motto, academic year, USN line, department name
- [x] Title block: Course Code, Date, Semester, Duration, CIE label, subject, "Answer all Questions"
- [x] SL.No/Questions/Marks/BT/CO question table with a repeating header across page breaks
- [x] Course Outcome description footer table, sourced from a per-subject CO1–CO5 editor (`/api/co-descriptions/{subject}`)
- [x] Marks Distribution footer table, computed automatically from the exam's actual question marks/CO/Bloom levels
- [x] Answer scheme export reuses the identical layout with the model answer + validation note printed under each question
- [x] "Publish to Students" captures the letterhead metadata (course code, semester, CIE label, exam date, academic year, department) once per exam
- [x] Round-trips through the answer-scheme parser — an exported PDF can be re-uploaded and parsed back into structured questions (see Module 2)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide React |
| Backend | FastAPI, Uvicorn, Python 3.11+ |
| Agent Pipeline | LangGraph, LangChain 0.3 |
| LLM | Ollama — Mistral (generation, text grading), LLaVA (scanned-answer OCR, drawing VLM), DeepSeek-R1 (numerical) |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — theory scoring + scanned-page-to-question similarity matching |
| Persistence | SQLite (`data/questions.db`, `data/eval_history.db`) |
| PDF Extraction | pypdf, PyMuPDF (fitz), LangChain PyPDFLoader — with multi-fallback |
| PDF Generation | ReportLab — college-format letterhead, question table, CO/marks footer |
| Document Loading | LangChain (PyPDF, Docx2txt, Unstructured) |
| Computer Vision | OpenCV (preprocessing), YOLOv8/Ultralytics (detection — stub) |
| Compliance | Custom IS/BIS rule engine (IS 696, SP:46, IS 919, IS 3073) |
| Legacy UI | Streamlit |

---

## What Still Needs Data (ME Team)

| Item | Volume | Used By |
|---|---|---|
| Theory Q&A pairs with keyword rubrics | 150+ questions across Thermodynamics, SOM, Fluid Mechanics | Theory evaluator validation |
| Numerical problems with step-level solution rubrics | 100+ problems with formula/expected value/units per step | Numerical grader validation |
| Hand-drawn engineering drawing photographs | 100+ drawings annotated with LabelImg | YOLOv8 fine-tuning |
| CO/PO Bloom-level mapping per subject per unit | Per faculty syllabus | Syllabus Guardian agent |

---

## Data

Subject materials under `data/raw/`:
- **BDT** — Units 1–5
- **Structural Mechanics** — Units 1–5
- **Propulsion** — Units 1–5
- **Structures** — Units 1–5

Previous year questions under `data/pyqs/` with pre-built ChromaDB stores at `data/db/chroma/`.
Generated questions auto-saved to `data/questions.db` (SQLite, created on first run).

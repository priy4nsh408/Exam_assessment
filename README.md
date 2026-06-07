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
2. **Theory Evaluation** — Two-tier LLM scoring (concept + detail) with ME keyword banks and cosine similarity
3. **Numerical Grading** — Step-level automated grading with 5-category error classification via chain-of-thought LLM
4. **Drawing Evaluation** — OpenCV preprocessing + YOLOv8 detection + LLaVA VLM + IS/BIS compliance engine
5. **Unified Dashboard** — React + TypeScript frontend with real-time SSE streaming, CO/PO analytics, and human-in-the-loop grade override

---

## Project Structure

```
Exam_assessment/
├── frontend/                    # React + TypeScript + Tailwind CSS dashboard
│   └── src/
│       ├── pages/               # 9 dashboard pages (all wired to real API)
│       ├── components/          # Sidebar, Header, StatCard, BloomBadge
│       ├── types/               # TypeScript entity types
│       └── api/                 # Fetch client
├── backend/
│   ├── main.py                  # FastAPI — 14 endpoints + SSE streaming
│   └── requirements.txt
├── generation/
│   ├── langgraph_pipeline.py    # 11-agent LangGraph pipeline + SQLite + SHA-256
│   └── generator.py             # Legacy single-agent Ollama generator
├── evaluation/
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
│   └── uploads/                 # Drawing image uploads (auto-created)
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

All 9 pages are wired to the real FastAPI backend with graceful fallbacks.

| Route | Page | API Used | Description |
|---|---|---|---|
| `/` | Dashboard | `/api/stats` | Stat cards, Bloom distribution, CO attainment bars, activity feed |
| `/generate` | Question Generator | `/api/questions/generate/stream` (SSE) | Live agent pipeline status, configure and generate questions |
| `/questions` | Question Bank | `/api/questions` | Search/filter all SQLite-backed questions |
| `/eval/theory` | Theory Evaluator | `/api/eval/theory` | Real keyword analysis, concept+detail scores, faculty override |
| `/eval/numerical` | Numerical Grader | `/api/eval/numerical` | Step-by-step breakdown with 5-category error classification |
| `/eval/drawing` | Drawing Evaluator | `/api/eval/drawing` | OpenCV pipeline, IS/BIS violation list, LLaVA JSON output |
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
| POST | `/api/exams` | Create an exam paper |
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

### Module 2 — Theory Answer Evaluation Engine
- [x] Frontend UI: upload, results list, keyword found/missing analysis, score breakdown, override form
- [x] Two-tier LLM scoring: concept score (0–5) + detail score (0–5) via Ollama
- [x] ME keyword banks for Thermodynamics, SOM, Fluid Mechanics, Engineering Drawing
- [x] Cosine similarity via sentence-transformers
- [x] `/api/eval/theory` endpoint — fully functional
- [ ] ME rubric dataset (150+ Q&A pairs with keyword annotations — **needs ME team**)
- [ ] Cohen's Kappa validation run against faculty scores

### Module 3 — Numerical Step-Level Grader
- [x] Frontend UI: step-by-step breakdown, 5-category error badges, partial credit display
- [x] LLM chain-of-thought step evaluator via Ollama
- [x] 5-category error classifier: formula / substitution / unit / arithmetic / boundary condition
- [x] Partial credit per step, heuristic fallback when LLM unavailable
- [x] `/api/eval/numerical` endpoint — fully functional
- [ ] ME numerical problem bank (100+ problems with step rubrics — **needs ME team**)
- [ ] Step-level accuracy validation (target ≥ 90%)

### Module 4 — Engineering Drawing Evaluator
- [x] Frontend UI: element detection grid, IS clause violation list, LLaVA JSON panel, upload
- [x] OpenCV preprocessing: CLAHE → Hough-line deskew → adaptive threshold → morphological denoise → 1024×768
- [x] YOLOv8 heuristic stub (quadrant-based element detection until trained weights available)
- [x] LLaVA VLM via Ollama for semantic JSON interpretation
- [x] IS/BIS compliance engine: IS 696:1972 (projection angle, view count), IS 919:1993 (tolerance notation), SP:46:2003 (title block), IS 3073:1967 (surface finish)
- [x] `/api/eval/drawing` endpoint with file upload — fully functional
- [ ] Annotated drawing dataset (100+ drawings — **needs ME team**)
- [ ] YOLOv8 fine-tuning on annotated dataset (use Google Colab T4 GPU)

### Module 5 — Unified Dashboard
- [x] React 18 + TypeScript + Vite + Tailwind CSS + Recharts frontend
- [x] All 9 pages wired to real FastAPI backend with graceful fallbacks
- [x] CO/PO analytics: bar chart, radar chart, trend line chart, CO–PO correlation matrix
- [x] Faculty override panel with confidence-based flagging and API-backed submission
- [x] Real-time SSE streaming for question generation with live agent status
- [x] SQLite-backed question bank with search, filter, delete

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide React |
| Backend | FastAPI, Uvicorn, Python 3.11+ |
| Agent Pipeline | LangGraph, LangChain 0.3 |
| LLM | Ollama — Mistral (generation), LLaVA (drawing VLM), DeepSeek-R1 (numerical) |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Persistence | SQLite (`data/questions.db`) |
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

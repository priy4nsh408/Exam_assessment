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

1. **Question Generation** — RAG pipeline generates syllabus-aligned questions with Bloom level, CO/PO tags
2. **Theory Evaluation** — LLM-based semantic grading with keyword rubrics
3. **Numerical Grading** — Step-level automated grading with 5-category error classification
4. **Drawing Evaluation** — Computer vision pipeline for hand-drawn engineering drawings with IS/BIS compliance
5. **Unified Dashboard** — React frontend with CO/PO analytics and human-in-the-loop grade override

---

## Project Structure

```
Exam_assessment/
├── frontend/                  # React + TypeScript + Tailwind CSS dashboard
│   └── src/
│       ├── pages/             # 9 dashboard pages
│       ├── components/        # Layout, UI primitives
│       ├── types/             # TypeScript types
│       └── api/               # API client
├── backend/                   # FastAPI REST API
│   ├── main.py                # 11 endpoints
│   └── requirements.txt
├── app/                       # Legacy Streamlit + CLI (still functional)
│   ├── streamlit_app.py
│   └── main.py
├── generation/                # Ollama-based question generation
├── ingestion/                 # PDF/DOCX/PPTX loader
├── chunking/                  # Text splitter
├── vector_store/              # ChromaDB client + retriever
├── pyq_processing/            # Previous year question parser
├── tagging/                   # Bloom's taxonomy + CO validation
├── data/
│   ├── raw/                   # Subject PDFs (BDT, Structural Mechanics, Propulsion, Structures)
│   ├── pyqs/                  # Previous year question papers
│   └── db/                    # Pre-built ChromaDB vector stores
└── requirements.txt           # Python dependencies
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
# Falls back to mock data if Ollama is not running
```

### Legacy Streamlit UI

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

### Environment

Create a `.env` file in the root:
```
OLLAMA_MODEL=mistral
```

---

## Dashboard Pages

| Route | Page | Description |
|---|---|---|
| `/` | Dashboard | Stat cards, Bloom distribution, CO attainment, activity feed |
| `/generate` | Question Generator | Configure subject/unit/Bloom/CO, run LangGraph pipeline, select questions |
| `/questions` | Question Bank | Search and filter all generated questions |
| `/eval/theory` | Theory Evaluator | Upload submissions, view keyword analysis and scores |
| `/eval/numerical` | Numerical Grader | Step-by-step grading with 5-category error breakdown |
| `/eval/drawing` | Drawing Evaluator | YOLOv8 detection, IS/BIS violation list, LLaVA output |
| `/analytics` | CO/PO Analytics | Bar, radar, trend charts + CO–PO correlation matrix |
| `/students` | Students | Per-student CO attainment table with At-Risk flagging |
| `/override` | Faculty Override | Review flagged grades, apply score overrides with reason |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/questions/generate` | Generate questions via RAG pipeline |
| GET | `/api/questions` | List questions (filterable by subject, type, bloom) |
| DELETE | `/api/questions/{id}` | Remove a question |
| GET | `/api/students` | Student roster |
| GET | `/api/submissions` | All submissions |
| POST | `/api/submissions/{id}/grade` | AI-grade a submission |
| POST | `/api/submissions/{id}/override` | Faculty override a grade |
| GET | `/api/analytics/co` | CO attainment data |
| GET | `/api/exams` | List exam papers |
| POST | `/api/exams` | Create an exam paper |

---

## Implementation Status

### Module 1 — Question Generation
- [x] ChromaDB vector store with sentence-transformers embeddings
- [x] RAG retrieval by subject and unit
- [x] Bloom level tagging and CO/PO mapping
- [x] Question generation via Ollama
- [ ] 11-agent LangGraph pipeline (Bloom Analyzer, Scout, Validator, Pedagogy Tagger, Syllabus Guardian, Archivist)
- [ ] SHA-256 deduplication across sessions
- [ ] SQLite persistence with provenance metadata
- [ ] FastAPI SSE streaming

### Module 2 — Theory Answer Evaluation
- [x] Frontend UI: upload, results, keyword analysis, score breakdown, override form
- [ ] LLaMA 3 / DeepSeek-R1 semantic grader
- [ ] spaCy ME keyword extractor
- [ ] Cosine similarity scoring engine
- [ ] ME rubric dataset (150+ Q&A pairs — needs ME team)

### Module 3 — Numerical Step-Level Grader
- [x] Frontend UI: step-by-step breakdown, 5-category error display
- [ ] DeepSeek-R1 tree-of-thought grader
- [ ] Step-level error classifier
- [ ] ME numerical problem bank (100+ problems — needs ME team)

### Module 4 — Engineering Drawing Evaluator
- [x] Frontend UI: element detection grid, IS clause violation list, LLaVA JSON panel
- [ ] OpenCV preprocessing pipeline
- [ ] YOLOv8 fine-tuned on ME drawing elements
- [ ] LLaVA / Qwen2-VL-7B VLM integration
- [ ] IS 696 / SP:46 / IS 919 / IS 3073 compliance engine
- [ ] Annotated drawing dataset (100+ drawings — needs ME team)

### Module 5 — Unified Dashboard
- [x] React + TypeScript frontend (all 9 pages)
- [x] CO/PO analytics with charts (bar, radar, trend, matrix)
- [x] Faculty override panel with confidence-based flagging
- [x] FastAPI backend with 11 endpoints
- [ ] Frontend wired to real AI outputs (currently shows realistic mock data)
- [ ] FastAPI SSE for live generation streaming

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide React |
| Backend | FastAPI, Uvicorn |
| LLM | Ollama (Mistral / LLaMA 3 / DeepSeek-R1 — local) |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Document Loading | LangChain (PyPDF, Docx2txt, Unstructured) |
| CV (planned) | OpenCV, YOLOv8 (Ultralytics), LLaVA / Qwen2-VL-7B |
| NLP (planned) | spaCy, HuggingFace |
| Legacy UI | Streamlit |

---

## Data

Subject materials are organized under `data/raw/`:
- **BDT** — Units 1–5 (PDFs)
- **Structural Mechanics** — Units 1–5
- **Propulsion** — Units 1–5
- **Structures** — Units 1–5

Previous year questions under `data/pyqs/` with pre-built ChromaDB stores at `data/db/chroma/`.

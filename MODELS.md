# MechAssess — Recommended AI Model Stack

The engine (`evaluation/engine/`) is fully provider-agnostic: every stage is
swappable via environment variables (see `evaluation/engine/config.py`).
This document explains **which model to use for each stage and why**.

## TL;DR — best combination

| Stage | Best (cloud) | Local fallback (built in) |
|---|---|---|
| Handwritten OCR | **Gemini 2.0 Flash** (vision) | Tesseract (print only) |
| Vision-Language (diagrams/graphs/flowcharts) | **GPT-4.1 / Gemini Flash** — same VLM call, diagrams transcribed as `[DIAGRAM: ...]` | text-signal heuristics |
| Grading LLM | **Claude Sonnet** or **GPT-4.1** | Ollama **Mistral 7B** |
| Mathematical reasoning | Claude / GPT-4.1 (step-wise rubric prompt) | step-detection heuristic |
| Embeddings (matching + RAG) | — | **all-MiniLM-L6-v2** (sentence-transformers, local, free) |
| RAG over answer schemes | ChromaDB + MiniLM (already in the repo) | same |

Enable the cloud stack by setting **any one** of:

```
GEMINI_API_KEY=...      # cheapest, excellent handwriting OCR
OPENAI_API_KEY=...      # GPT-4.1 — strongest all-rounder
ANTHROPIC_API_KEY=...   # Claude — best grading explanations
```

No key set → the system still works fully offline with Tesseract + Ollama
Mistral + MiniLM, but handwriting OCR quality drops sharply (Tesseract is a
print-OCR engine).

## Stage-by-stage rationale

### 1. Handwritten OCR
- **Gemini 2.0 Flash** — best price/quality for messy student handwriting,
  handles equations, tables, and describes diagrams inline. Our prompt makes it
  emit `[DIAGRAM: ...]`, `[GRAPH: ...]`, `[TABLE ...]` markers that downstream
  evaluators consume.
- **GPT-4.1 (vision)** — equal quality, higher cost.
- **TrOCR / PaddleOCR** — good line-level handwriting models but need layout
  detection + line segmentation glue and struggle with equations/diagrams;
  not worth the complexity vs a VLM.
- **Nougat** — designed for *printed* academic PDFs (papers → markdown), not
  handwriting. Not suitable here.
- **Tesseract** — kept as offline fallback; fine for typed/printed scripts.

### 2. Question detection & answer matching
Regex handles `Q1 / Question 1 / Ans 1 / 1.` variants; **MiniLM embeddings**
semantically match un-numbered or shuffled answers to the answer scheme.
Local, instant, free — no reason to use a cloud model here.

### 3. Grading (theory / numerical / derivation / diagram / flowchart / graph)
One rubric-driven examiner prompt per type (`evaluation/engine/evaluate.py`).
- **Claude Sonnet** — best at faithful rubric mapping and explanation quality
  ("why marks were awarded"), lowest hallucinated-deduction rate.
- **GPT-4.1** — equally strong, slightly better on long numerical chains.
- **Llama 3.1 70B / Mistral Large** — viable self-hosted options if data must
  stay on-prem; Mistral 7B via Ollama is the built-in local fallback (works,
  but expect ±1-2 marks variance on 10-mark questions).

### 4. Confidence & review routing
Deterministic weighted formula (no model): OCR 30% + grader confidence 30% +
rubric coverage 15% + match certainty 15% + completeness 10%.
`< 80%` → faculty review queue. `< 35%` OCR → illegible, no auto-marks.

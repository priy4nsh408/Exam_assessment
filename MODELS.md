# MechAssess — Model Stack

MechAssess runs **entirely on your own machine via [Ollama](https://ollama.ai)** —
no cloud API, no account, no usage limits. This document explains which
Ollama model to use for each stage and why.

## TL;DR

| Stage | Model | Setup |
|---|---|---|
| Handwriting reading + grading | **`llava`** (default) | `ollama pull llava` |
| Stronger handwriting/diagram reading (if your machine can run it) | `llama3.2-vision` | `ollama pull llama3.2-vision` |
| Fastest, lowest-resource option | `moondream` | `ollama pull moondream` |
| Text-only grading fallback (typed PDFs, Paste Answers) | `mistral` (default) | `ollama pull mistral` |
| Embeddings (matching answers to the scheme) | `all-MiniLM-L6-v2` | bundled via `sentence-transformers`, no separate pull needed |

Set `OLLAMA_VISION_MODEL=llama3.2-vision` (or any other pulled vision model)
in a `.env` file at the project root to switch — no code changes needed.

## Stage-by-stage rationale

### 1. Handwriting reading + grading (one call)
Page images go straight to the local vision model together with the answer
scheme, and it reads the handwriting **and** grades every answer against the
rubric in a single response — no separate OCR step.
- **`llava`** — best balance of size and quality for messy student handwriting,
  handles equations, tables, and describes diagrams inline (as `[DIAGRAM: ...]`,
  `[GRAPH: ...]` in its transcription).
- **`llama3.2-vision`** — stronger reading and reasoning if your machine has the
  RAM/GPU to run it comfortably.
- **`moondream`** — tiny and fast, lower accuracy; good for quick iteration on
  weaker hardware.

### 2. Question detection & answer matching
Regex handles `Q1 / Question 1 / Ans 1 / 1.` variants; **MiniLM embeddings**
semantically match un-numbered or shuffled answers to the answer scheme.
Fully local, instant, no model download beyond the one-time `sentence-transformers`
weights.

### 3. Text-only grading fallback
Used for typed/digital PDFs (no handwriting to read) and the **Paste Answers**
tab. `mistral` via Ollama grades against the rubric; if Ollama isn't reachable
at all, a deterministic keyword+semantic grader still produces marks (clearly
labelled `keyword_semantic` in the report) so grading never simply fails.

### 4. Confidence & review routing
Deterministic weighted formula (no model call): reading confidence 30% +
grader confidence 30% + rubric coverage 15% + match certainty 15% +
completeness 10%. Below the threshold → flagged for a faculty second look —
**marks are never withheld or zeroed for low confidence**; the answer scheme
is always the final word on scoring, and faculty override handles the rest.

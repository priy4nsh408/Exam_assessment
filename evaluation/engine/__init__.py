"""
MechAssess Evaluation Engine v2 — fully local, Ollama-only
============================================================
Closed-loop AI evaluation of handwritten answer scripts. No cloud API, no
Tesseract OCR engine — handwriting is read and graded by a local Ollama
vision model (llava by default).

Pipeline stages (see pipeline.py for the orchestrator):

  1. Reading        — ocr.py + vision_eval.py   blank-page detection, PyMuPDF
                                     for typed PDFs, Ollama vision for handwriting
  2. Detection      — detect.py     question-number detection (Q1 / Question 1 / Ans 1 / 1.)
                                     + question-type classification
  3. Segmentation   — segment.py    split script into per-answer segments,
                                     semantic matching to answer scheme (shuffled order OK)
  4. Evaluation     — evaluate.py   rubric-based grading per question type
                                     with deterministic fallbacks
  5. Confidence     — confidence.py weighted confidence score, <80% → flagged for review
                                     (never withholds marks — the scheme is always the master)
  6. Reports        — reports.py    student / faculty / class analytics
"""

from evaluation.engine.pipeline import evaluate_script  # noqa: F401

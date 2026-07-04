"""
MechAssess Evaluation Engine v2
================================
Closed-loop AI evaluation of handwritten answer scripts.

Pipeline stages (see pipeline.py for the orchestrator):

  1. OCR            — ocr.py        PyMuPDF text → VLM/Tesseract for handwriting,
                                     blank-page detection, per-page confidence
  2. Detection      — detect.py     question-number detection (Q1 / Question 1 / Ans 1 / 1.)
                                     + question-type classification
  3. Segmentation   — segment.py    split script into per-answer segments,
                                     semantic matching to answer scheme (shuffled order OK)
  4. Evaluation     — evaluate.py   rubric-based LLM grading per question type
                                     with deterministic fallbacks
  5. Confidence     — confidence.py weighted confidence engine, <80% → faculty review
  6. Reports        — reports.py    student / faculty / class analytics
"""

from evaluation.engine.pipeline import evaluate_script  # noqa: F401

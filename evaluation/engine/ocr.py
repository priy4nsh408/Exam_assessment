"""
Stage 1 — Page reading (typed text + blank detection)
======================================================
This module handles only what doesn't need AI:

  1. Blank-page detection (ink-coverage) — blank pages are skipped, never
     evaluated, never penalised.
  2. PyMuPDF direct text extraction — instant for typed/digital PDFs, no OCR
     needed since the text is already embedded in the file.

Actually reading HANDWRITING is done by the local Ollama vision model
(evaluation.engine.vision_eval) — there is no OCR engine and no cloud API
in this pipeline. If a page has no embedded text and Ollama vision isn't
available, the page is honestly reported as unread rather than guessed at.
"""

from __future__ import annotations
import os
import tempfile
from typing import Dict, List

from evaluation.engine.config import get_config

try:
    import fitz as _fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def dependency_status() -> Dict:
    cfg = get_config()
    try:
        from evaluation.engine.vision_eval import ollama_vision_ready
        vision_ready = ollama_vision_ready()
    except Exception:
        vision_ready = False
    err = "" if vision_ready else (
        f"Ollama vision isn't ready — install Ollama (https://ollama.ai), then run: "
        f"ollama pull {cfg.ollama_vision_model}"
    )
    return {
        "pymupdf":   {"available": PYMUPDF_AVAILABLE, "error": "" if PYMUPDF_AVAILABLE else "pip install pymupdf"},
        "cloud_vlm": {"available": vision_ready, "error": err, "via": "ollama" if vision_ready else ""},
        "pillow":    {"available": True, "error": ""},
        "ready":     PYMUPDF_AVAILABLE,
    }


# ── Rendering & blank detection ───────────────────────────────────────────────

def _render_page(page, out_path: str, dpi: int) -> str:
    mat = _fitz.Matrix(dpi / 72, dpi / 72)
    page.get_pixmap(matrix=mat, colorspace=_fitz.csRGB).save(out_path)
    return out_path


def _ink_coverage(image_path: str) -> float:
    """Fraction of pixels that are 'ink' (significantly darker than paper)."""
    try:
        from PIL import Image
        img = Image.open(image_path).convert("L")
        img.thumbnail((400, 400))
        px = list(img.getdata())
        if not px:
            return 0.0
        return sum(1 for p in px if p < 160) / len(px)
    except Exception:
        pass
    # Pillow-free path via PyMuPDF
    try:
        pix = _fitz.Pixmap(image_path)
        if pix.n > 1:
            pix = _fitz.Pixmap(_fitz.csGRAY, pix)
        samples = pix.samples
        step = max(1, len(samples) // 160000)  # subsample for speed
        px = samples[::step]
        return sum(1 for p in px if p < 160) / max(1, len(px))
    except Exception:
        return 1.0  # if we can't check, assume not blank


def is_blank_page(image_path: str, text: str = "") -> bool:
    if text.strip():
        return False
    cfg = get_config()
    return _ink_coverage(image_path) < cfg.blank_page_ink_threshold


# ── Public entry points ────────────────────────────────────────────────────────

def page_images(file_path: str) -> List[Dict]:
    """
    Render pages to images WITHOUT running any OCR — used by the vision-grading
    path, which sends the images straight to the local Ollama vision model.
    Returns [{page, image_path, blank}]. Blank pages are flagged.
    """
    cfg = get_config()
    out: List[Dict] = []
    if file_path.lower().endswith(".pdf"):
        if not PYMUPDF_AVAILABLE:
            raise RuntimeError("PyMuPDF is required — pip install pymupdf")
        doc = _fitz.open(file_path)
        tmp_dir = tempfile.mkdtemp(prefix="mechassess_img_")
        for i, page in enumerate(doc, start=1):
            embedded = page.get_text("text").strip()
            img_path = os.path.join(tmp_dir, f"page_{i:03d}.png")
            _render_page(page, img_path, dpi=cfg.ocr_dpi)
            out.append({"page": i, "image_path": img_path,
                        "blank": is_blank_page(img_path, embedded)})
        doc.close()
    else:
        out.append({"page": 1, "image_path": file_path,
                    "blank": is_blank_page(file_path, "")})
    return out


def ocr_document(file_path: str) -> List[Dict]:
    """
    Read a PDF or image into page records using ONLY the embedded digital
    text layer (no OCR engine, no cloud). Handwritten/scanned pages with no
    text layer are honestly reported as unread (empty text, 0 confidence) —
    reading those requires the Ollama vision path (see vision_eval.py).
    Returns: [{page, text, image_path, confidence, low_confidence, blank, method}]
    """
    if file_path.lower().endswith(".pdf"):
        return _read_pdf(file_path)
    return [_read_page_image(file_path, page_no=1, embedded_text="")]


def _read_pdf(pdf_path: str) -> List[Dict]:
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF is required — pip install pymupdf")

    cfg = get_config()
    doc = _fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="mechassess_read_")
    pages: List[Dict] = []

    for i, page in enumerate(doc, start=1):
        embedded = page.get_text("text").strip()
        img_path = os.path.join(tmp_dir, f"page_{i:03d}.png")
        _render_page(page, img_path, dpi=cfg.ocr_dpi)
        pages.append(_read_page_image(img_path, page_no=i, embedded_text=embedded))

    doc.close()
    return pages


def _read_page_image(image_path: str, page_no: int, embedded_text: str) -> Dict:
    rec = {
        "page": page_no,
        "image_path": image_path,
        "text": "",
        "confidence": 0.0,
        "low_confidence": True,
        "blank": False,
        "method": "unread",
    }

    # Blank page → skip entirely (never evaluated, never penalised)
    if is_blank_page(image_path, embedded_text):
        rec.update({"blank": True, "confidence": 1.0, "low_confidence": False, "method": "blank_detect"})
        return rec

    # Digital text layer → done, perfect confidence, no AI needed
    if len(embedded_text) > 30:
        rec.update({"text": embedded_text, "confidence": 1.0, "low_confidence": False, "method": "pymupdf_text"})
        return rec

    # Handwritten/scanned with no text layer: this module does not attempt to
    # read it — that's the local Ollama vision model's job (the primary path
    # in pipeline.py). Report honestly as unread rather than guessing.
    return rec

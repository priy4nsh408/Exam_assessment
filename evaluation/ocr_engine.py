"""
OCR Engine for handwritten answer scripts.

Priority order for PDF text extraction:
  1. PyMuPDF (fitz)  — direct text extraction, no system deps, works for typed PDFs
  2. pdf2image + EasyOCR — converts to images then deep-learning OCR, best for handwriting
  3. EasyOCR on image  — for image files (PNG/JPG)

PyMuPDF is the recommended path for answer schemes (typed PDFs).
EasyOCR is the recommended path for handwritten student answer scripts.
"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple

# ── PyMuPDF (fitz) — no system deps, works for typed/digital PDFs ─────────────
try:
    import fitz as _fitz
    PYMUPDF_AVAILABLE = True
    PYMUPDF_ERROR = ""
except ImportError:
    PYMUPDF_AVAILABLE = False
    PYMUPDF_ERROR = "PyMuPDF not installed. Run: pip install pymupdf"

# ── pdf2image ────────────────────────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
    PDF2IMAGE_ERROR = ""
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    PDF2IMAGE_ERROR = "pdf2image not installed. Run: pip install pdf2image"

# ── EasyOCR ──────────────────────────────────────────────────────────────────
try:
    import easyocr as _easyocr
    _reader: "_easyocr.Reader | None" = None

    def _get_reader() -> "_easyocr.Reader":
        global _reader
        if _reader is None:
            _reader = _easyocr.Reader(["en"], gpu=False, verbose=False)
        return _reader

    EASYOCR_AVAILABLE = True
    EASYOCR_ERROR = ""
except ImportError:
    EASYOCR_AVAILABLE = False
    EASYOCR_ERROR = "easyocr not installed. Run: pip install easyocr"

# ── Pillow ───────────────────────────────────────────────────────────────────
try:
    from PIL import Image as _PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def get_dependency_status() -> Dict:
    return {
        "pdf2image":  {"available": PDF2IMAGE_AVAILABLE, "error": PDF2IMAGE_ERROR},
        "pymupdf":    {"available": PYMUPDF_AVAILABLE,   "error": PYMUPDF_ERROR},
        "easyocr":    {"available": EASYOCR_AVAILABLE,   "error": EASYOCR_ERROR},
        "pillow":     {"available": PIL_AVAILABLE,        "error": "" if PIL_AVAILABLE else "Pillow not installed"},
        "ready":      EASYOCR_AVAILABLE and (PDF2IMAGE_AVAILABLE or PYMUPDF_AVAILABLE),
    }


# ── PyMuPDF text extraction (typed/digital PDFs) ──────────────────────────────

def extract_text_pymupdf(pdf_path: str) -> List[Dict]:
    """
    Extract text directly from a digital PDF using PyMuPDF.
    No poppler, no OCR, no system dependencies.
    Returns same format as ocr_pdf: [{page, text, image_path, confidence, low_confidence}]
    """
    doc = _fitz.open(pdf_path)
    pages: List[Dict] = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        pages.append({
            "page":           i,
            "text":           text,
            "image_path":     "",
            "confidence":     1.0 if text else 0.0,
            "low_confidence": not bool(text),
            "method":         "pymupdf",
        })
    doc.close()
    return pages


# ── pdf2image + EasyOCR (handwritten/scanned PDFs) ───────────────────────────

def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[str]:
    """Convert every PDF page to a PNG. Returns list of image paths."""
    if not PDF2IMAGE_AVAILABLE:
        raise RuntimeError(
            "pdf2image not installed or poppler not in PATH. "
            "Run: pip install pdf2image  and install poppler (see README)."
        )
    tmp_dir = tempfile.mkdtemp(prefix="mechassess_ocr_")
    pages = convert_from_path(pdf_path, dpi=dpi, output_folder=tmp_dir, fmt="png")
    paths: List[str] = []
    for i, page in enumerate(pages):
        out = os.path.join(tmp_dir, f"page_{i+1:03d}.png")
        page.save(out, "PNG")
        paths.append(out)
    return paths


def ocr_image_with_confidence(image_path: str) -> Tuple[str, float]:
    """Run EasyOCR on a single image. Returns (text, avg_confidence)."""
    if not EASYOCR_AVAILABLE:
        return "[OCR unavailable — install easyocr]", 0.0
    reader = _get_reader()
    results = reader.readtext(image_path, detail=1, paragraph=False)
    if not results:
        return "", 0.0
    texts = [r[1] for r in results]
    confs  = [float(r[2]) for r in results]
    return "\n".join(texts), sum(confs) / len(confs)


def ocr_pdf(pdf_path: str) -> List[Dict]:
    """
    Full PDF pipeline — automatically chooses best method:
      1. PyMuPDF for typed/digital PDFs (fast, no deps)
      2. pdf2image + EasyOCR for scanned/handwritten PDFs
    Returns: [{page, text, image_path, confidence, low_confidence}]
    """
    # Try PyMuPDF first (fast, works for typed answer schemes)
    if PYMUPDF_AVAILABLE:
        try:
            pages = extract_text_pymupdf(pdf_path)
            # If meaningful text was extracted, use it
            total_text = " ".join(p["text"] for p in pages).strip()
            if len(total_text) > 50:
                return pages
        except Exception:
            pass

    # Fall back to pdf2image + EasyOCR (handwritten scripts)
    image_paths = pdf_to_images(pdf_path)
    pages: List[Dict] = []
    for i, img_path in enumerate(image_paths, start=1):
        text, conf = ocr_image_with_confidence(img_path)
        pages.append({
            "page":           i,
            "text":           text,
            "image_path":     img_path,
            "confidence":     round(conf, 3),
            "low_confidence": conf < 0.6,
            "method":         "easyocr",
        })
    return pages


def ocr_image_file(image_path: str) -> List[Dict]:
    """Single image entry point. Returns same format as ocr_pdf."""
    text, conf = ocr_image_with_confidence(image_path)
    return [{
        "page":           1,
        "text":           text,
        "image_path":     image_path,
        "confidence":     round(conf, 3),
        "low_confidence": conf < 0.6,
        "method":         "easyocr",
    }]


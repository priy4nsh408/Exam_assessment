"""
OCR Engine for handwritten answer scripts.
Converts PDF pages to images then runs EasyOCR (deep-learning based,
better for messy handwriting than Tesseract).
Returns per-page confidence scores and surfaces missing-dependency errors clearly.
"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple

# ── pdf2image ────────────────────────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
    PDF2IMAGE_ERROR = ""
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    PDF2IMAGE_ERROR = "pdf2image not installed. Run: pip install pdf2image && apt-get install -y poppler-utils"

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
    """Return install status of optional OCR dependencies."""
    return {
        "pdf2image": {"available": PDF2IMAGE_AVAILABLE, "error": PDF2IMAGE_ERROR},
        "easyocr": {"available": EASYOCR_AVAILABLE, "error": EASYOCR_ERROR},
        "pillow": {"available": PIL_AVAILABLE, "error": "" if PIL_AVAILABLE else "Pillow not installed"},
        "ready": PDF2IMAGE_AVAILABLE and EASYOCR_AVAILABLE,
    }


def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[str]:
    """Convert every PDF page to a PNG in a temp dir. Returns list of paths."""
    if not PDF2IMAGE_AVAILABLE:
        raise RuntimeError(PDF2IMAGE_ERROR)
    tmp_dir = tempfile.mkdtemp(prefix="mechassess_ocr_")
    pages = convert_from_path(pdf_path, dpi=dpi, output_folder=tmp_dir, fmt="png")
    paths: List[str] = []
    for i, page in enumerate(pages):
        out = os.path.join(tmp_dir, f"page_{i+1:03d}.png")
        page.save(out, "PNG")
        paths.append(out)
    return paths


def ocr_image_with_confidence(image_path: str) -> Tuple[str, float]:
    """
    Run OCR on a single image.
    Returns (text, avg_confidence) where confidence is 0-1.
    """
    if not EASYOCR_AVAILABLE:
        if PIL_AVAILABLE:
            _PILImage.open(image_path)
        return "[OCR unavailable — install easyocr]", 0.0

    reader = _get_reader()
    # detail=1 returns (bbox, text, confidence)
    results = reader.readtext(image_path, detail=1, paragraph=False)
    if not results:
        return "", 0.0

    texts = [r[1] for r in results]
    confidences = [float(r[2]) for r in results]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return "\n".join(texts), avg_conf


def ocr_pdf(pdf_path: str) -> List[Dict]:
    """
    Full pipeline: PDF → per-page images → OCR.
    Returns: [{page, text, image_path, confidence, low_confidence}]
    """
    image_paths = pdf_to_images(pdf_path)
    pages: List[Dict] = []
    for i, img_path in enumerate(image_paths, start=1):
        text, conf = ocr_image_with_confidence(img_path)
        pages.append({
            "page": i,
            "text": text,
            "image_path": img_path,
            "confidence": round(conf, 3),
            "low_confidence": conf < 0.6,
        })
    return pages


def ocr_image_file(image_path: str) -> List[Dict]:
    """Single-image entry point. Returns same format as ocr_pdf."""
    text, conf = ocr_image_with_confidence(image_path)
    return [{
        "page": 1,
        "text": text,
        "image_path": image_path,
        "confidence": round(conf, 3),
        "low_confidence": conf < 0.6,
    }]

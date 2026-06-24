"""
OCR Engine for handwritten answer scripts.
Converts PDF pages to images then runs EasyOCR (deep-learning based,
better for messy handwriting than Tesseract).
Falls back gracefully when dependencies are missing.
"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import List, Dict

# ── pdf2image ────────────────────────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

# ── EasyOCR ──────────────────────────────────────────────────────────────────
try:
    import easyocr
    _reader: easyocr.Reader | None = None

    def _get_reader() -> easyocr.Reader:
        global _reader
        if _reader is None:
            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return _reader

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# ── Pillow (used as fallback image saver) ────────────────────────────────────
try:
    from PIL import Image as _PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[str]:
    """
    Convert every page of a PDF to a PNG saved in a temp directory.
    Returns list of absolute image paths (one per page).
    """
    if not PDF2IMAGE_AVAILABLE:
        raise RuntimeError(
            "pdf2image is not installed. Run: pip install pdf2image\n"
            "Also ensure poppler is available: apt-get install -y poppler-utils"
        )
    tmp_dir = tempfile.mkdtemp(prefix="mechassess_ocr_")
    pages = convert_from_path(pdf_path, dpi=dpi, output_folder=tmp_dir, fmt="png")
    paths: List[str] = []
    for i, page in enumerate(pages):
        out = os.path.join(tmp_dir, f"page_{i+1:03d}.png")
        page.save(out, "PNG")
        paths.append(out)
    return paths


def ocr_image(image_path: str) -> str:
    """
    Run OCR on a single image. Returns extracted text as a string.
    Uses EasyOCR when available; falls back to a stub message.
    """
    if EASYOCR_AVAILABLE:
        reader = _get_reader()
        results = reader.readtext(image_path, detail=0, paragraph=True)
        return "\n".join(results)

    # Pillow stub — can at least confirm the file loads
    if PIL_AVAILABLE:
        _PILImage.open(image_path)  # verify readable
    return "[OCR not available — install easyocr: pip install easyocr]"


def ocr_pdf(pdf_path: str) -> List[Dict]:
    """
    Full pipeline: PDF → per-page images → OCR text.
    Returns list of dicts: {page: int, text: str, image_path: str}
    """
    image_paths = pdf_to_images(pdf_path)
    pages: List[Dict] = []
    for i, img_path in enumerate(image_paths, start=1):
        text = ocr_image(img_path)
        pages.append({"page": i, "text": text, "image_path": img_path})
    return pages


def ocr_image_file(image_path: str) -> List[Dict]:
    """
    Single-image entry point (PNG / JPEG uploads).
    Returns same format as ocr_pdf for uniform handling.
    """
    text = ocr_image(image_path)
    return [{"page": 1, "text": text, "image_path": image_path}]

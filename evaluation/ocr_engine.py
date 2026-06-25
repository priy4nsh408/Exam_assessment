"""
OCR Engine for answer scripts.

Pipeline (in priority order):
  1. PyMuPDF direct text extraction  — instant, perfect for typed/digital PDFs
  2. PyMuPDF page→image + Tesseract  — fast, good for scanned/handwritten PDFs
                                        no poppler, no EasyOCR, no GPU needed
"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple

# ── PyMuPDF ──────────────────────────────────────────────────────────────────
try:
    import fitz as _fitz
    PYMUPDF_AVAILABLE = True
    PYMUPDF_ERROR = ""
except ImportError:
    PYMUPDF_AVAILABLE = False
    PYMUPDF_ERROR = "PyMuPDF not installed. Run: pip install pymupdf"

# ── Tesseract (via pytesseract) ───────────────────────────────────────────────
try:
    import pytesseract as _tess
    from PIL import Image as _PILImage
    # Quick smoke-test so we know tesseract binary is actually present
    _tess.get_tesseract_version()
    TESSERACT_AVAILABLE = True
    TESSERACT_ERROR = ""
except Exception as _te:
    TESSERACT_AVAILABLE = False
    TESSERACT_ERROR = str(_te)

PIL_AVAILABLE = True
try:
    from PIL import Image as _PILImage  # noqa: F811
except ImportError:
    PIL_AVAILABLE = False


def get_dependency_status() -> Dict:
    return {
        "pymupdf":    {"available": PYMUPDF_AVAILABLE,   "error": PYMUPDF_ERROR},
        "tesseract":  {"available": TESSERACT_AVAILABLE, "error": TESSERACT_ERROR},
        "pillow":     {"available": PIL_AVAILABLE,        "error": "" if PIL_AVAILABLE else "Pillow not installed"},
        # legacy keys kept so existing health-check UI doesn't break
        "pdf2image":  {"available": True,  "error": ""},
        "easyocr":    {"available": True,  "error": ""},
        "ready":      PYMUPDF_AVAILABLE,
    }


# ── 1. PyMuPDF direct text extraction ────────────────────────────────────────

def _extract_text_pymupdf(pdf_path: str) -> List[Dict]:
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
            "method":         "pymupdf_text",
        })
    doc.close()
    return pages


# ── 2. PyMuPDF → image → Tesseract ───────────────────────────────────────────

def _render_page_to_image(page: "_fitz.Page", out_path: str, dpi: int = 200) -> str:
    """Render a single PDF page to a PNG file using PyMuPDF (no poppler needed)."""
    mat = _fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=_fitz.csRGB)
    pix.save(out_path)
    return out_path


def _tesseract_on_image(image_path: str) -> Tuple[str, float]:
    """
    Run Tesseract on an image file.
    PSM 3 = fully automatic page segmentation (best for mixed handwriting/print).
    PSM 6 tried as fallback if PSM 3 returns nothing.
    """
    if not TESSERACT_AVAILABLE:
        return "", 0.0

    try:
        import pytesseract as _tess
        from PIL import Image as _PILImage

        img = _PILImage.open(image_path)
        # Upscale small images — Tesseract works better at higher resolution
        w, h = img.size
        if w < 1500:
            scale = 1500 / w
            img = img.resize((int(w * scale), int(h * scale)), _PILImage.LANCZOS)

        best_text = ""
        best_conf = 0.0
        for psm in ("3", "6", "4"):
            cfg = f"--psm {psm} --oem 3"
            try:
                data = _tess.image_to_data(img, config=cfg, output_type=_tess.Output.DICT)
                confs = [int(c) / 100.0 for c in data["conf"] if int(c) > 0]
                text  = _tess.image_to_string(img, config=cfg).strip()
                avg   = sum(confs) / len(confs) if confs else 0.0
                if len(text) > len(best_text):
                    best_text, best_conf = text, avg
            except Exception:
                continue
        return best_text, best_conf
    except Exception as e:
        return "", 0.0


def _pdf_to_images_pymupdf(pdf_path: str, dpi: int = 200) -> List[str]:
    """Render all PDF pages to PNGs using PyMuPDF. No poppler required."""
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF not installed — run: pip install pymupdf")

    doc = _fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="mechassess_ocr_")
    paths: List[str] = []
    for i, page in enumerate(doc, start=1):
        out = os.path.join(tmp_dir, f"page_{i:03d}.png")
        _render_page_to_image(page, out, dpi=dpi)
        paths.append(out)
    doc.close()
    return paths


# ── Public entry points ───────────────────────────────────────────────────────

def ocr_pdf(pdf_path: str) -> List[Dict]:
    """
    Full PDF pipeline:
      1. Try PyMuPDF direct text extraction (instant — works for digital PDFs)
      2. Fall back to PyMuPDF→image + Tesseract (fast — works for scanned/handwritten)
    Returns: [{page, text, image_path, confidence, low_confidence, method}]
    """
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF is required. Run: pip install pymupdf")

    # Step 1 — direct text extraction
    try:
        pages = _extract_text_pymupdf(pdf_path)
        total_text = " ".join(p["text"] for p in pages).strip()
        if len(total_text) > 50:
            return pages           # typed/digital PDF — done in milliseconds
    except Exception:
        pass

    # Step 2 — render to images then Tesseract
    image_paths = _pdf_to_images_pymupdf(pdf_path, dpi=200)
    pages_out: List[Dict] = []
    for i, img_path in enumerate(image_paths, start=1):
        text, conf = _tesseract_on_image(img_path)
        pages_out.append({
            "page":           i,
            "text":           text,
            "image_path":     img_path,
            "confidence":     round(conf, 3),
            "low_confidence": conf < 0.6,
            "method":         "tesseract",
        })
    return pages_out


def ocr_image_file(image_path: str) -> List[Dict]:
    """Single image entry point. Returns same format as ocr_pdf."""
    text, conf = _tesseract_on_image(image_path)
    return [{
        "page":           1,
        "text":           text,
        "image_path":     image_path,
        "confidence":     round(conf, 3),
        "low_confidence": conf < 0.6,
        "method":         "tesseract",
    }]

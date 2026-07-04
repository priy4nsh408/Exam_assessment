"""
Stage 1 — OCR
=============
Intelligent handwritten OCR with layered strategies:

  1. Blank-page detection (ink-coverage) — blank pages are skipped, never
     evaluated, never penalised.
  2. PyMuPDF direct text extraction — instant for typed/digital PDFs.
  3. Cloud Vision-Language OCR (Gemini / GPT-4.1 / Claude vision) — best for
     handwriting; used automatically when an API key is configured.
  4. Tesseract — local fallback (good for print, weak on handwriting).

Every page record preserves: page number, text, image path, confidence,
method, blank flag — answer position is preserved because segmentation
works on the concatenated in-order text with page offsets.
"""

from __future__ import annotations
import base64
import os
import tempfile
from typing import Dict, List, Optional, Tuple

from evaluation.engine.config import get_config

try:
    import fitz as _fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract as _tess
    from PIL import Image as _PILImage
    _tess.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def dependency_status() -> Dict:
    cfg = get_config()
    cloud_vlm = bool(cfg.gemini_api_key or cfg.openai_api_key or cfg.anthropic_api_key)
    return {
        "pymupdf":   {"available": PYMUPDF_AVAILABLE, "error": "" if PYMUPDF_AVAILABLE else "pip install pymupdf"},
        "tesseract": {"available": TESSERACT_AVAILABLE, "error": "" if TESSERACT_AVAILABLE else "install tesseract-ocr + pip install pytesseract"},
        "cloud_vlm": {"available": cloud_vlm, "error": "" if cloud_vlm else "set GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY for handwriting OCR"},
        "pillow":    {"available": True, "error": ""},
        # legacy keys so old health-check UI doesn't break
        "pdf2image": {"available": True, "error": ""},
        "easyocr":   {"available": True, "error": ""},
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


# ── OCR backends ──────────────────────────────────────────────────────────────

_VLM_OCR_PROMPT = (
    "Transcribe ALL handwritten and printed content on this exam answer page. "
    "Preserve line breaks and the order content appears. "
    "Write mathematical expressions in plain text (e.g. sigma = F/A, x^2). "
    "If there is a diagram, describe it on its own line as: [DIAGRAM: <what it shows, labels visible>]. "
    "If there is a table, transcribe it row by row. "
    "If there is a graph, describe axes, labels and the trend as [GRAPH: ...]. "
    "Keep question numbers exactly as written (Q1, Ans 3, 5) etc.). "
    "Output only the transcription, nothing else."
)


def _b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _vlm_ocr_gemini(image_path: str) -> Optional[str]:
    cfg = get_config()
    r = _requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent",
        params={"key": cfg.gemini_api_key},
        json={"contents": [{"parts": [
            {"text": _VLM_OCR_PROMPT},
            {"inline_data": {"mime_type": "image/png", "data": _b64(image_path)}},
        ]}]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _vlm_ocr_openai(image_path: str) -> Optional[str]:
    cfg = get_config()
    r = _requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
        json={
            "model": cfg.openai_model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": _VLM_OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(image_path)}"}},
            ]}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _vlm_ocr_anthropic(image_path: str) -> Optional[str]:
    cfg = get_config()
    r = _requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": cfg.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": cfg.anthropic_model,
            "max_tokens": 3000,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _b64(image_path)}},
                {"type": "text", "text": _VLM_OCR_PROMPT},
            ]}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def _vlm_ocr(image_path: str) -> Tuple[Optional[str], str]:
    """Try cloud vision OCR in priority order. Returns (text, provider)."""
    cfg = get_config()
    if not REQUESTS_AVAILABLE or cfg.vlm_ocr == "off":
        return None, ""
    attempts = []
    if cfg.gemini_api_key:
        attempts.append(("gemini", _vlm_ocr_gemini))
    if cfg.openai_api_key:
        attempts.append(("openai", _vlm_ocr_openai))
    if cfg.anthropic_api_key:
        attempts.append(("anthropic", _vlm_ocr_anthropic))
    for name, fn in attempts:
        try:
            text = fn(image_path)
            if text and text.strip():
                return text.strip(), name
        except Exception:
            continue
    return None, ""


def _tesseract_ocr(image_path: str) -> Tuple[str, float]:
    """Local Tesseract with PSM cycling + upscaling. Returns (text, confidence)."""
    if not TESSERACT_AVAILABLE:
        return "", 0.0
    try:
        img = _PILImage.open(image_path)
        w, h = img.size
        if w < 1500:
            scale = 1500 / w
            img = img.resize((int(w * scale), int(h * scale)), _PILImage.LANCZOS)
        best_text, best_conf = "", 0.0
        for psm in ("3", "6", "4"):
            cfg = f"--psm {psm} --oem 3"
            try:
                data = _tess.image_to_data(img, config=cfg, output_type=_tess.Output.DICT)
                confs = [int(c) / 100.0 for c in data["conf"] if int(c) > 0]
                text = _tess.image_to_string(img, config=cfg).strip()
                avg = sum(confs) / len(confs) if confs else 0.0
                if len(text) > len(best_text):
                    best_text, best_conf = text, avg
            except Exception:
                continue
        return best_text, best_conf
    except Exception:
        return "", 0.0


# ── Public entry point ────────────────────────────────────────────────────────

def ocr_document(file_path: str) -> List[Dict]:
    """
    OCR a PDF or image into page records:
      [{page, text, image_path, confidence, low_confidence, blank, method}]
    Blank pages are flagged (blank=True) and carry empty text.
    """
    if file_path.lower().endswith(".pdf"):
        return _ocr_pdf(file_path)
    return [_ocr_page_image(file_path, page_no=1, embedded_text="")]


def _ocr_pdf(pdf_path: str) -> List[Dict]:
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF is required — pip install pymupdf")

    cfg = get_config()
    doc = _fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="mechassess_ocr_")
    pages: List[Dict] = []

    for i, page in enumerate(doc, start=1):
        embedded = page.get_text("text").strip()
        img_path = os.path.join(tmp_dir, f"page_{i:03d}.png")
        _render_page(page, img_path, dpi=cfg.ocr_dpi)
        pages.append(_ocr_page_image(img_path, page_no=i, embedded_text=embedded))

    doc.close()
    return pages


def _ocr_page_image(image_path: str, page_no: int, embedded_text: str) -> Dict:
    rec = {
        "page": page_no,
        "image_path": image_path,
        "text": "",
        "confidence": 0.0,
        "low_confidence": True,
        "blank": False,
        "method": "none",
    }

    # Blank page → skip entirely (never evaluated, never penalised)
    if is_blank_page(image_path, embedded_text):
        rec.update({"blank": True, "confidence": 1.0, "low_confidence": False, "method": "blank_detect"})
        return rec

    # Digital text layer → done, perfect confidence
    if len(embedded_text) > 30:
        rec.update({"text": embedded_text, "confidence": 1.0, "low_confidence": False, "method": "pymupdf_text"})
        return rec

    # Cloud VLM (best for handwriting)
    vlm_text, provider = _vlm_ocr(image_path)
    if vlm_text:
        rec.update({"text": vlm_text, "confidence": 0.92, "low_confidence": False, "method": f"vlm_{provider}"})
        return rec

    # Tesseract fallback
    text, conf = _tesseract_ocr(image_path)
    rec.update({
        "text": text,
        "confidence": round(conf, 3),
        "low_confidence": conf < 0.6,
        "method": "tesseract",
    })
    return rec

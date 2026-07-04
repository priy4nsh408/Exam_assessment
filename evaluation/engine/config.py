"""
Engine configuration — everything is env-driven so the model stack can be
swapped without code changes.

Recommended stack (see MODELS.md at repo root for the full comparison):
  OCR (handwriting)  : Gemini 2.x Flash / GPT-4.1 vision  (cloud, best)
                       → Tesseract fallback (local, print-quality only)
  Embeddings         : sentence-transformers all-MiniLM-L6-v2 (local)
  Grading LLM        : Claude / GPT-4.1 (cloud)  → Ollama Mistral (local fallback)
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

# Load API keys from a .env file at the repo root (if present) so users can
# put GEMINI_API_KEY=... in Exam_assessment/.env instead of setting env vars.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass


@dataclass
class EngineConfig:
    # ── LLM grading ──────────────────────────────────────────────
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "mistral"))
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "30"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))

    # ── Vision OCR for handwriting (uses same cloud keys) ────────
    # "auto" = use best available cloud VLM, else Tesseract
    vlm_ocr: str = field(default_factory=lambda: os.getenv("VLM_OCR", "auto"))
    ocr_dpi: int = int(os.getenv("OCR_DPI", "200"))

    # ── Thresholds ───────────────────────────────────────────────
    review_confidence_threshold: float = float(os.getenv("REVIEW_THRESHOLD", "0.80"))
    illegible_ocr_threshold: float = float(os.getenv("ILLEGIBLE_THRESHOLD", "0.35"))
    blank_page_ink_threshold: float = float(os.getenv("BLANK_INK_THRESHOLD", "0.005"))
    semantic_match_threshold: float = float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.35"))

    # ── Embeddings ───────────────────────────────────────────────
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )


_config: EngineConfig | None = None


def get_config() -> EngineConfig:
    global _config
    if _config is None:
        _config = EngineConfig()
    return _config

"""
Engine configuration — Ollama-only, fully local, no cloud API keys.

Stack:
  Handwriting reading + grading : Ollama vision model (llava by default)
  Text grading fallback         : Ollama text model (mistral by default)
  Embeddings                    : sentence-transformers all-MiniLM-L6-v2 (local)

Everything runs on this machine. No API keys, no quotas, no internet needed
after the one-time `ollama pull`.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

# Load settings from a .env file at the repo root (if present).
# Works even if python-dotenv isn't installed (manual fallback parser).
def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    try:
        from dotenv import load_dotenv
        if load_dotenv(env_path):
            return
    except ImportError:
        pass
    try:
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


_load_env_file()


@dataclass
class EngineConfig:
    # ── Ollama (local, no API key) ────────────────────────────────
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "mistral"))
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "30"))
    # Vision model for reading + grading handwriting: llava (default),
    # llama3.2-vision (stronger, bigger), or moondream (tiny, fastest).
    ollama_vision_model: str = field(default_factory=lambda: os.getenv("OLLAMA_VISION_MODEL", "llava"))
    ollama_vision_timeout: int = int(os.getenv("OLLAMA_VISION_TIMEOUT", "180"))

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

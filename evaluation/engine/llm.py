"""
LLM access layer — Ollama only, fully local, no API keys.
==========================================================
One function: chat_json(prompt) → parsed dict or None.

Used for text-only grading (typed PDFs where handwriting reading isn't
needed). Runs against the local Ollama text model with a hard timeout so a
missing Ollama daemon never hangs an evaluation — falls back to the
deterministic keyword+semantic grader instead.
"""

from __future__ import annotations
import json
import re
import threading
from typing import Optional, Dict, Any

from evaluation.engine.config import get_config


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first JSON object out of an LLM response (handles ```json fences)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip("` \n")
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _ollama_chat(prompt: str, system: str, timeout: int) -> Optional[str]:
    """Local Ollama with hard timeout via daemon thread (never hangs)."""
    try:
        import ollama
    except ImportError:
        return None

    cfg = get_config()
    holder: list = [None]

    def _call():
        try:
            resp = ollama.chat(
                model=cfg.ollama_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.1},
            )
            holder[0] = resp["message"]["content"]
        except Exception:
            pass

    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return holder[0]


def chat_json(prompt: str, system: str = "You are a strict but fair university examiner.") -> Optional[Dict[str, Any]]:
    """Send a prompt expecting a JSON reply. Returns parsed dict or None."""
    cfg = get_config()
    raw = _ollama_chat(prompt, system, cfg.ollama_timeout)
    if raw:
        return _extract_json(raw)
    return None


def llm_available() -> bool:
    """Best-effort: Ollama package is importable. Actual reachability is
    checked at call time by _ollama_chat's timeout/None-return behaviour."""
    try:
        import ollama  # noqa: F401
        return True
    except ImportError:
        return False

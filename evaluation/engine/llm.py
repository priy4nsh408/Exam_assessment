"""
LLM access layer — one function: chat_json(prompt) → parsed dict or None.

Provider priority:
  1. Anthropic Claude  (ANTHROPIC_API_KEY set)
  2. OpenAI GPT        (OPENAI_API_KEY set)
  3. Google Gemini     (GEMINI_API_KEY set)
  4. Ollama local      (always tried last, hard timeout so a missing
                        Ollama daemon never hangs an evaluation)

Every call has a hard timeout. On total failure returns None and the
caller falls back to deterministic (keyword + semantic) grading.
"""

from __future__ import annotations
import json
import re
import threading
from typing import Optional, Dict, Any

from evaluation.engine.config import get_config

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first JSON object out of an LLM response (handles ```json fences)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip("` \n")
    # find outermost braces
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


# ── Cloud providers (plain HTTPS, no SDK dependency) ─────────────────────────

def _anthropic_chat(prompt: str, system: str, timeout: int) -> Optional[str]:
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
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def _openai_chat(prompt: str, system: str, timeout: int) -> Optional[str]:
    cfg = get_config()
    r = _requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
        json={
            "model": cfg.openai_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _gemini_chat(prompt: str, system: str, timeout: int) -> Optional[str]:
    cfg = get_config()
    r = _requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent",
        params={"key": cfg.gemini_api_key},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


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
    providers = []
    if REQUESTS_AVAILABLE and cfg.anthropic_api_key:
        providers.append(_anthropic_chat)
    if REQUESTS_AVAILABLE and cfg.openai_api_key:
        providers.append(_openai_chat)
    if REQUESTS_AVAILABLE and cfg.gemini_api_key:
        providers.append(_gemini_chat)
    providers.append(_ollama_chat)

    for provider in providers:
        try:
            raw = provider(prompt, system, cfg.ollama_timeout)
        except Exception:
            raw = None
        if raw:
            parsed = _extract_json(raw)
            if parsed is not None:
                return parsed
    return None


def llm_available() -> bool:
    cfg = get_config()
    return bool(cfg.anthropic_api_key or cfg.openai_api_key or cfg.gemini_api_key) or True

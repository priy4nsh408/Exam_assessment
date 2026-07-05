"""
Vision grading — Ollama only, fully local, no API keys.
========================================================
Send the handwritten answer-script page images STRAIGHT to a local Ollama
vision model (llava by default) together with the answer scheme. The model
reads the handwriting AND grades every answer against the scheme in a single
call. No separate OCR step, no cloud, no API key.

Why this is better than OCR-then-grade:
  • vision models read messy handwriting, equations, diagrams and tables far
    better than a text-only OCR engine
  • answers in any order (Q5 → Q1 → Q8) are matched by the model itself
  • blank pages / rough work are ignored by the model
  • one call → transcription + rubric marks + explanation per question

Requires Ollama running locally with a vision model pulled:
    ollama pull llava
Returns per-question answer records in the same shape the pipeline expects,
or None if Ollama isn't reachable (caller falls back to the typed-text path).
"""

from __future__ import annotations
import base64
import json
import re
from typing import Dict, List, Optional

from evaluation.engine.config import get_config

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def ollama_vision_ready() -> bool:
    """Is Ollama running locally with the configured vision model pulled?"""
    if not REQUESTS_AVAILABLE:
        return False
    cfg = get_config()
    try:
        r = _requests.get(f"{cfg.ollama_host}/api/tags", timeout=2)
        if r.status_code != 200:
            return False
        names = [m.get("name", "").split(":")[0] for m in r.json().get("models", [])]
        return cfg.ollama_vision_model in names
    except Exception:
        return False


def vision_available() -> bool:
    return ollama_vision_ready()


# Records the real reason the last vision attempt failed, so it can be
# surfaced instead of silently falling back.
LAST_ERROR: str = ""


def selftest() -> Dict:
    """
    Make a REAL minimal Ollama call and report the actual result/error —
    the honest 'is my local AI working?' check.
    """
    cfg = get_config()
    out: Dict = {"requests_installed": REQUESTS_AVAILABLE, "providers": {}}
    if not REQUESTS_AVAILABLE:
        out["error"] = "python 'requests' package not installed (pip install requests)"
        return out

    try:
        r = _requests.get(f"{cfg.ollama_host}/api/tags", timeout=3)
        if r.status_code != 200:
            out["providers"]["ollama_vision"] = {
                "ok": False,
                "error": f"Ollama not responding at {cfg.ollama_host} (HTTP {r.status_code}). Is `ollama serve` running?",
            }
        else:
            names = [m.get("name", "").split(":")[0] for m in r.json().get("models", [])]
            if cfg.ollama_vision_model not in names:
                out["providers"]["ollama_vision"] = {
                    "ok": False,
                    "error": f"Ollama is running but '{cfg.ollama_vision_model}' isn't pulled. "
                            f"Run: ollama pull {cfg.ollama_vision_model}  (models found: {names or 'none'})",
                }
            else:
                # Model is pulled — actually exercise /api/chat the same way real
                # grading does, so version-specific quirks are caught here too.
                try:
                    _ollama_chat_call(cfg, [], "Reply with the single word OK", timeout=30, use_format_json=True)
                    out["providers"]["ollama_vision"] = {
                        "ok": True, "model": cfg.ollama_vision_model,
                        "note": "Local vision model ready — fully offline, no API key needed.",
                    }
                except Exception:
                    try:
                        _ollama_chat_call(cfg, [], "Reply with the single word OK", timeout=30, use_format_json=False)
                        out["providers"]["ollama_vision"] = {
                            "ok": True, "model": cfg.ollama_vision_model,
                            "note": "Local vision model ready (compatibility mode for this Ollama version).",
                        }
                    except Exception as e2:
                        out["providers"]["ollama_vision"] = {
                            "ok": False,
                            "error": f"Ollama has '{cfg.ollama_vision_model}' pulled but /api/chat rejected the "
                                    f"request: {e2}. Try: winget upgrade Ollama.Ollama, or a different model "
                                    f"(ollama pull llama3.2-vision).",
                        }
    except Exception as e:
        out["providers"]["ollama_vision"] = {
            "ok": False,
            "error": f"Could not reach Ollama at {cfg.ollama_host} ({e}). Install from https://ollama.ai, "
                    f"then run: ollama pull {cfg.ollama_vision_model}",
        }

    out["any_working"] = any(p.get("ok") for p in out["providers"].values())
    return out


def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


_SYSTEM = (
    "You are a strict but fair university examiner for Mechanical Engineering. "
    "You are given photos/scans of a student's HANDWRITTEN exam answer script "
    "and the official ANSWER SCHEME. The answer scheme is the absolute master. "
    "Read the handwriting carefully (including equations, diagrams, tables, graphs) "
    "and grade every question strictly against the scheme and its rubric.\n"
    "Rules you MUST follow:\n"
    "• Award marks — do not withhold. Even partially correct answers get partial marks.\n"
    "• Numericals: grade step-wise (formula, substitution, calculation, final answer, "
    "units). Give method marks even if the final answer is wrong.\n"
    "• Never require exact wording — accept synonyms, equivalent definitions and "
    "alternate correct methods. Accept equivalent diagrams (concept, not pixels).\n"
    "• Do NOT invent mistakes or deductions that aren't grounded in the rubric.\n"
    "• Answers may appear in any order and may span multiple pages. Match each answer "
    "to the correct question by its content. Ignore blank pages and rough work.\n"
    "• If a question was clearly not attempted, award 0 and say 'not attempted'.\n"
    "Respond with ONE JSON object only, no prose."
)


def _build_prompt(exam: Dict) -> str:
    scheme = exam.get("questions") or []
    subject = exam.get("subject") or "Mechanical Engineering"
    ginstr = exam.get("marking_instructions") or ""

    lines = [f"SUBJECT: {subject}"]
    if ginstr:
        lines.append(f"GLOBAL MARKING INSTRUCTIONS: {ginstr}")
    lines.append("\nANSWER SCHEME (grade against this exactly):")
    for q in scheme:
        qn = q.get("q_number")
        mm = q.get("max_marks", 10)
        lines.append(f"\nQ{qn} (max {mm} marks){' [' + q['type'] + ']' if q.get('type') else ''}:")
        if q.get("question"):
            lines.append(f"  Question: {q['question']}")
        if q.get("reference_answer"):
            lines.append(f"  Reference answer: {q['reference_answer']}")
        rubric = q.get("rubric") or []
        if rubric:
            rub = "; ".join(f"{r['criterion']}={r['marks']}" for r in rubric)
            lines.append(f"  Rubric: {rub}")
        if q.get("marking_instructions"):
            lines.append(f"  Instructions: {q['marking_instructions']}")

    qnums = [q.get("q_number") for q in scheme]
    lines.append(
        "\nThe following page images are the student's handwritten answer script. "
        "Grade every scheme question. Return JSON:\n"
        '{"answers":[{'
        '"q_number":<int>,'
        '"transcription":"<what the student wrote, your reading of the handwriting>",'
        '"awarded_marks":<number>,'
        '"max_marks":<number>,'
        '"rubric_mapping":[{"criterion":"...","max":<n>,"awarded":<n>,"reason":"..."}],'
        '"covered":["points the student got right"],'
        '"missing":["required points that are absent/wrong"],'
        '"strengths":["..."],"weaknesses":["..."],"suggestions":["..."],'
        '"feedback":"2-3 sentences on why these marks",'
        '"attempted":<true|false>,'
        '"confidence":<0..1 how sure you are you read the handwriting correctly>'
        "}]}\n"
        f"Produce one entry for each of these questions: {qnums}."
    )
    return "\n".join(lines)


# ── Ollama call ───────────────────────────────────────────────────────────────

def _ollama_chat_call(cfg, images_b64: List[str], prompt: str, timeout: int, use_format_json: bool) -> str:
    payload = {
        "model": cfg.ollama_vision_model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt, "images": images_b64},
        ],
        "stream": False,
    }
    if use_format_json:
        payload["format"] = "json"
    r = _requests.post(f"{cfg.ollama_host}/api/chat", json=payload, timeout=timeout)
    if r.status_code != 200:
        # Surface Ollama's actual error body instead of a generic "400 Bad Request"
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
    return r.json()["message"]["content"]


def _ollama_vision(image_paths: List[str], prompt: str, timeout: int) -> Optional[str]:
    """
    Local vision grading via Ollama — NO API key, NO internet needed after
    the one-time model download. Requires a vision-capable model pulled
    locally, e.g.:  ollama pull llava   (or llama3.2-vision / moondream)
    """
    cfg = get_config()
    images_b64 = [_b64(p) for p in image_paths]
    t = max(timeout, cfg.ollama_vision_timeout)
    try:
        return _ollama_chat_call(cfg, images_b64, prompt, t, use_format_json=True)
    except Exception as e:
        # Some Ollama versions reject "format": "json" alongside images — retry without it.
        if "format" in str(e).lower() or "400" in str(e):
            return _ollama_chat_call(cfg, images_b64, prompt, t, use_format_json=False)
        raise


def _extract_json(text: str) -> Optional[Dict]:
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
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def transcribe_pages(image_paths: List[str]) -> Optional[str]:
    """
    Plain transcription (no grading) via the local Ollama vision model — used
    to parse scanned/handwritten answer schemes when there's no embedded
    text layer to read directly. Returns None if Ollama isn't reachable.
    """
    if not ollama_vision_ready() or not image_paths:
        return None
    cfg = get_config()
    prompt = (
        "Transcribe ALL text on these pages exactly, preserving line breaks, "
        "question numbers, and structure. Do not summarize, explain, or add "
        "commentary — output only the raw transcription."
    )
    try:
        images_b64 = [_b64(p) for p in image_paths[:15]]
        return _ollama_chat_call(cfg, images_b64, prompt, timeout=cfg.ollama_vision_timeout, use_format_json=False)
    except Exception:
        return None


def grade_script_vision(image_paths: List[str], exam: Dict) -> Optional[List[Dict]]:
    """
    Grade a whole handwritten script from its page images against the scheme,
    using the local Ollama vision model. Returns pipeline-shaped answer
    records, or None if Ollama isn't reachable / didn't return usable JSON.
    """
    global LAST_ERROR
    LAST_ERROR = ""

    if not ollama_vision_ready() or not image_paths:
        if not REQUESTS_AVAILABLE:
            LAST_ERROR = "python 'requests' package not installed"
        else:
            LAST_ERROR = "Ollama not reachable or vision model not pulled"
        return None

    image_paths = image_paths[:15]  # keep the payload sane
    prompt = _build_prompt(exam)

    try:
        raw = _ollama_vision(image_paths, prompt, timeout=120)
    except Exception as e:
        LAST_ERROR = f"ollama: {e}"
        raw = None
    if not raw:
        return None

    parsed = _extract_json(raw)
    if not parsed or "answers" not in parsed:
        LAST_ERROR = "ollama: response was not valid JSON with an 'answers' array"
        return None

    q_map = {int(q["q_number"]): q for q in (exam.get("questions") or []) if q.get("q_number")}
    records: List[Dict] = []
    for a in parsed["answers"]:
        try:
            qn = int(a.get("q_number"))
        except (TypeError, ValueError):
            continue
        meta = q_map.get(qn, {})
        max_marks = float(a.get("max_marks") or meta.get("max_marks") or 10)
        awarded = a.get("awarded_marks", 0)
        try:
            awarded = max(0.0, min(max_marks, float(awarded)))
        except (TypeError, ValueError):
            awarded = 0.0

        mapping = []
        for r in (a.get("rubric_mapping") or []):
            try:
                mx = float(r.get("max", 0)); aw = max(0.0, min(mx, float(r.get("awarded", 0))))
                mapping.append({"criterion": str(r.get("criterion", "")), "max": mx,
                                "awarded": aw, "reason": str(r.get("reason", ""))})
            except (TypeError, ValueError):
                continue

        attempted = a.get("attempted", True)
        conf = a.get("confidence", 0.85)
        try:
            conf = max(0.0, min(1.0, float(conf)))
        except (TypeError, ValueError):
            conf = 0.85

        records.append({
            "q_number": qn,
            "q_type": (meta.get("type") or "theory"),
            "question": meta.get("question") or f"Question {qn}",
            "ocr_text": str(a.get("transcription", "")),
            "ocr_confidence": conf,
            "low_confidence": conf < 0.6,
            "image_paths": image_paths,
            "page_start": 1,
            "matched_by": "vision",
            "match_similarity": None,
            "ai_score": round(awarded, 1),
            "max_score": max_marks,
            "rubric_mapping": mapping or [{"criterion": "Overall", "max": max_marks,
                                           "awarded": round(awarded, 1), "reason": str(a.get("feedback", ""))}],
            "feedback": str(a.get("feedback", "")),
            "covered": [str(x) for x in (a.get("covered") or [])][:10],
            "missing": [str(x) for x in (a.get("missing") or [])][:10],
            "strengths": [str(x) for x in (a.get("strengths") or [])][:6],
            "weaknesses": [str(x) for x in (a.get("weaknesses") or [])][:6],
            "suggestions": [str(x) for x in (a.get("suggestions") or [])][:6],
            "expected_answer": (meta.get("reference_answer") or "")[:1200],
            "grading_method": "vision_ollama",
            "model_confidence": conf,
            "attempted": bool(attempted),
        })

    return records or None

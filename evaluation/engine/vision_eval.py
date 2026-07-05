"""
Vision grading — the primary evaluation path.
=============================================
Send the handwritten answer-script page images STRAIGHT to a vision-language
model together with the answer scheme. The model reads the handwriting AND
grades every answer against the scheme in a single call. No separate OCR step.

Why this is better than OCR-then-grade:
  • vision models read messy handwriting, equations, diagrams and tables far
    better than Tesseract
  • answers in any order (Q5 → Q1 → Q8) are matched by the model itself
  • blank pages / rough work are ignored by the model
  • one call → transcription + rubric marks + explanation per question

Providers (first with a key wins): Gemini → OpenAI → Anthropic.
Returns per-question answer records in the same shape the pipeline expects,
or None if no vision provider is reachable (caller falls back to OCR path).
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


def vision_available() -> bool:
    cfg = get_config()
    return REQUESTS_AVAILABLE and bool(
        cfg.gemini_api_key or cfg.openai_api_key or cfg.anthropic_api_key
    )


# Records the real reason the last vision attempt failed, so it can be surfaced
# instead of silently falling back to OCR.
LAST_ERROR: str = ""
LAST_MODEL_USED: str = ""

# Some AI Studio keys get a free-tier quota of exactly 0 for specific models
# (commonly the newest release, e.g. gemini-2.0-flash) while other models on
# the SAME key work fine. Try the configured model first, then fall back
# across other commonly-available free-tier models rather than failing.
_GEMINI_FALLBACK_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]


def selftest() -> Dict:
    """
    Make a REAL minimal API call to every configured provider and report the
    actual result/error. This is the honest 'is my key working?' check.
    """
    cfg = get_config()
    out: Dict = {"requests_installed": REQUESTS_AVAILABLE, "providers": {}}
    if not REQUESTS_AVAILABLE:
        out["error"] = "python 'requests' package not installed (pip install requests)"
        return out

    if cfg.gemini_api_key:
        models_to_try = [cfg.gemini_model] + [m for m in _GEMINI_FALLBACK_MODELS if m != cfg.gemini_model]
        attempts = []
        found_working = None
        for model in models_to_try:
            try:
                r = _requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": cfg.gemini_api_key},
                    json={"contents": [{"parts": [{"text": "Reply with the single word OK"}]}]},
                    timeout=30,
                )
                if r.status_code == 200:
                    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    attempts.append({"model": model, "ok": True, "reply": txt[:40]})
                    found_working = model
                    break
                attempts.append({"model": model, "ok": False, "status": r.status_code, "error": r.text[:300]})
            except Exception as e:
                attempts.append({"model": model, "ok": False, "error": str(e)[:300]})
        if found_working:
            out["providers"]["gemini"] = {
                "ok": True, "model": found_working,
                "reply": attempts[-1]["reply"],
                "note": (f"Configured model '{cfg.gemini_model}' didn't work but '{found_working}' does — "
                         f"the app will automatically use '{found_working}'.") if found_working != cfg.gemini_model else "",
            }
        else:
            out["providers"]["gemini"] = {
                "ok": False, "model": cfg.gemini_model,
                "error": f"All models failed. Tried: {[a['model'] for a in attempts]}. "
                        f"Last error: {attempts[-1].get('error', '')}",
                "attempts": attempts,
            }
    else:
        out["providers"]["gemini"] = {"ok": False, "error": "no GEMINI_API_KEY set"}

    if cfg.openai_api_key:
        try:
            r = _requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
                json={"model": cfg.openai_model, "messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 5},
                timeout=30,
            )
            out["providers"]["openai"] = {"ok": r.status_code == 200, "model": cfg.openai_model,
                                          "status": r.status_code, "error": "" if r.status_code == 200 else r.text[:400]}
        except Exception as e:
            out["providers"]["openai"] = {"ok": False, "error": str(e)[:400]}

    if cfg.anthropic_api_key:
        try:
            r = _requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": cfg.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": cfg.anthropic_model, "max_tokens": 5, "messages": [{"role": "user", "content": "Reply OK"}]},
                timeout=30,
            )
            out["providers"]["anthropic"] = {"ok": r.status_code == 200, "model": cfg.anthropic_model,
                                             "status": r.status_code, "error": "" if r.status_code == 200 else r.text[:400]}
        except Exception as e:
            out["providers"]["anthropic"] = {"ok": False, "error": str(e)[:400]}

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


# ── Provider calls ────────────────────────────────────────────────────────────

def _gemini_call_once(model: str, image_paths: List[str], prompt: str, timeout: int) -> str:
    cfg = get_config()
    parts: List[Dict] = [{"text": prompt}]
    for p in image_paths:
        parts.append({"inline_data": {"mime_type": "image/png", "data": _b64(p)}})
    r = _requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": cfg.gemini_api_key},
        json={
            "system_instruction": {"parts": [{"text": _SYSTEM}]},
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _gemini(image_paths: List[str], prompt: str, timeout: int) -> Optional[str]:
    global LAST_ERROR, LAST_MODEL_USED
    cfg = get_config()
    models_to_try = [cfg.gemini_model] + [m for m in _GEMINI_FALLBACK_MODELS if m != cfg.gemini_model]

    last_exc: Optional[Exception] = None
    for model in models_to_try:
        try:
            text = _gemini_call_once(model, image_paths, prompt, timeout)
            LAST_MODEL_USED = model
            return text
        except Exception as e:
            last_exc = e
            msg = str(e)
            # 429 quota / 404 model-not-found → try the next model in the list
            if "429" in msg or "404" in msg or "quota" in msg.lower():
                continue
            break  # any other error (auth, network) won't be fixed by switching models
    if last_exc:
        raise last_exc
    return None


def _openai(image_paths: List[str], prompt: str, timeout: int) -> Optional[str]:
    cfg = get_config()
    content: List[Dict] = [{"type": "text", "text": prompt}]
    for p in image_paths:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_b64(p)}"}})
    r = _requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
        json={
            "model": cfg.openai_model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": content},
            ],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _anthropic(image_paths: List[str], prompt: str, timeout: int) -> Optional[str]:
    cfg = get_config()
    content: List[Dict] = []
    for p in image_paths:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": _b64(p)}})
    content.append({"type": "text", "text": prompt})
    r = _requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": cfg.anthropic_api_key,
                 "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": cfg.anthropic_model, "max_tokens": 4000, "system": _SYSTEM,
              "messages": [{"role": "user", "content": content}]},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


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


def grade_script_vision(image_paths: List[str], exam: Dict) -> Optional[List[Dict]]:
    """
    Grade a whole handwritten script from its page images against the scheme.
    Returns pipeline-shaped answer records, or None if no provider succeeded.
    """
    if not vision_available() or not image_paths:
        return None

    cfg = get_config()
    image_paths = image_paths[:15]  # keep the payload sane
    prompt = _build_prompt(exam)

    providers = []
    if cfg.gemini_api_key:
        providers.append(("gemini", _gemini))
    if cfg.openai_api_key:
        providers.append(("openai", _openai))
    if cfg.anthropic_api_key:
        providers.append(("anthropic", _anthropic))

    global LAST_ERROR
    LAST_ERROR = ""
    raw = None
    used = ""
    for name, fn in providers:
        try:
            raw = fn(image_paths, prompt, timeout=120)
            if raw:
                used = name
                break
        except Exception as e:
            LAST_ERROR = f"{name}: {e}"
            raw = None
    if not raw:
        return None

    parsed = _extract_json(raw)
    if not parsed or "answers" not in parsed:
        LAST_ERROR = f"{used}: response was not valid JSON with an 'answers' array"
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
            "grading_method": f"vision_{used}",
            "model_confidence": conf,
            "attempted": bool(attempted),
        })

    return records or None

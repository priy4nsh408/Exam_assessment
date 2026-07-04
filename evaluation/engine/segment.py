"""
Stage 3 — Answer segmentation & semantic matching
=================================================
Splits the OCR'd script into per-answer segments, then matches each segment
to a question in the answer scheme.

Matching is SEMANTIC, not positional:
  • A detected "Q5" marker claims question 5 — accepted if the scheme has Q5.
  • Un-numbered segments are matched by embedding similarity between the
    student's answer and each scheme question+reference answer.
  • Shuffled order (Q5 → Q1 → Q8) is fully supported.
  • If two segments claim the same question, the semantically closer one wins
    and the other is re-matched.

Each segment carries: q_number, text, image_paths, page_start, ocr_confidence,
diagram_refs (lines like [DIAGRAM: ...]), math_expressions, matched_by.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional

from evaluation.engine.detect import find_question_markers
from evaluation.engine.embeddings import similarity_matrix
from evaluation.engine.config import get_config

_MATH_RX = re.compile(
    r"([A-Za-zσετρμΔθπ]\s*=\s*[^,\n]{2,60}|\d+(?:\.\d+)?\s*(?:MPa|kPa|kN|N|mm|m/s|rpm|W|J|K|°C)\b)"
)
_DIAGRAM_RX = re.compile(r"\[(DIAGRAM|GRAPH|FLOWCHART|TABLE)[^\]]*\]", re.I)


def _extract_features(text: str) -> Dict:
    return {
        "math_expressions": _MATH_RX.findall(text)[:20],
        "diagram_refs": _DIAGRAM_RX.findall(text.upper())[:10] and _DIAGRAM_RX.findall(text)[:10],
    }


def segment_script(pages: List[Dict], scheme_questions: Optional[List[Dict]] = None) -> List[Dict]:
    """
    pages: OCR page records (blank pages already flagged).
    scheme_questions: [{q_number, question, reference_answer, max_marks, ...}]
    Returns list of answer segments.
    """
    live_pages = [p for p in pages if not p.get("blank")]
    if not live_pages:
        return []

    # Concatenate text preserving page offsets (keeps answer position info)
    full_text = ""
    offsets: List[tuple] = []  # (char_offset, page_no, image_path, confidence)
    for p in live_pages:
        offsets.append((len(full_text), p["page"], p["image_path"], p.get("confidence", 1.0)))
        full_text += p["text"] + "\n\n"

    max_q = max((int(q.get("q_number", 0)) for q in scheme_questions), default=20) if scheme_questions else 20
    markers = find_question_markers(full_text, max_q=max(max_q, 20))

    def _page_info(offset: int):
        info = offsets[0]
        for rec in offsets:
            if rec[0] <= offset:
                info = rec
        return info  # (char_offset, page_no, image_path, confidence)

    segments: List[Dict] = []
    if markers:
        for i, (s, e, q) in enumerate(markers):
            end = markers[i + 1][0] if i + 1 < len(markers) else len(full_text)
            body = full_text[e:end].strip()
            if len(body) < 5:
                continue
            _, page_no, img, conf = _page_info(s)
            # collect all page images the segment spans
            end_page = _page_info(max(end - 1, s))[1]
            span_imgs = [rec[2] for rec in offsets if page_no <= rec[1] <= end_page]
            segments.append({
                "q_number": q,
                "claimed_q": q,
                "text": body,
                "image_paths": span_imgs or [img],
                "page_start": page_no,
                "ocr_confidence": conf,
                "matched_by": "detected_number",
                **_extract_features(body),
            })
    else:
        # No markers at all → one segment per page, to be matched semantically
        for p in live_pages:
            if not p["text"].strip():
                continue
            segments.append({
                "q_number": 0,
                "claimed_q": None,
                "text": p["text"].strip(),
                "image_paths": [p["image_path"]],
                "page_start": p["page"],
                "ocr_confidence": p.get("confidence", 1.0),
                "matched_by": "unmatched",
                **_extract_features(p["text"]),
            })

    if scheme_questions:
        segments = match_to_scheme(segments, scheme_questions)

    for s in segments:
        s["low_confidence"] = s["ocr_confidence"] < 0.6
    return segments


def match_to_scheme(segments: List[Dict], scheme: List[Dict]) -> List[Dict]:
    """
    Reconcile segments with the answer scheme using semantic similarity.
    Handles: shuffled answers, missing numbers, duplicate claims.
    """
    cfg = get_config()
    scheme_by_q = {int(q["q_number"]): q for q in scheme if q.get("q_number")}
    scheme_texts = [
        f"{q.get('question','')} {q.get('reference_answer','')[:800]}" for q in scheme
    ]
    seg_texts = [s["text"][:1500] for s in segments]
    sims = similarity_matrix(seg_texts, scheme_texts) if segments and scheme else []

    taken: Dict[int, int] = {}  # q_number -> segment index

    def _best_free_match(si: int) -> Optional[int]:
        ranked = sorted(range(len(scheme)), key=lambda j: -sims[si][j])
        for j in ranked:
            qn = int(scheme[j].get("q_number", 0))
            if qn and qn not in taken and sims[si][j] >= cfg.semantic_match_threshold:
                return qn
        return None

    # Pass 1: honour detected numbers that exist in the scheme
    for i, seg in enumerate(segments):
        cq = seg.get("claimed_q")
        if cq and cq in scheme_by_q:
            if cq in taken:
                # conflict: keep the semantically closer segment
                other = taken[cq]
                j = next((k for k, q in enumerate(scheme) if int(q.get("q_number", 0)) == cq), None)
                if j is not None and sims and sims[i][j] > sims[other][j]:
                    segments[other]["claimed_q"] = None
                    segments[other]["matched_by"] = "conflict_rematched"
                    taken[cq] = i
                else:
                    seg["claimed_q"] = None
                    seg["matched_by"] = "conflict_rematched"
            else:
                taken[cq] = i

    # Pass 2: semantic matching for everything unassigned
    for i, seg in enumerate(segments):
        assigned = any(v == i for v in taken.values())
        if assigned:
            continue
        qn = _best_free_match(i) if sims else None
        if qn:
            taken[qn] = i
            seg["matched_by"] = "semantic"
        else:
            seg["matched_by"] = "unmatched"

    # Finalize q_number + attach similarity score
    for qn, si in taken.items():
        segments[si]["q_number"] = qn
        j = next((k for k, q in enumerate(scheme) if int(q.get("q_number", 0)) == qn), None)
        segments[si]["match_similarity"] = round(sims[si][j], 3) if (sims and j is not None) else None

    # Drop segments that matched nothing and look like rough work
    result = []
    for i, seg in enumerate(segments):
        if any(v == i for v in taken.values()):
            result.append(seg)
        elif seg["matched_by"] == "unmatched" and len(seg["text"]) < 80:
            continue  # rough work / stray fragment
        else:
            seg["q_number"] = seg.get("claimed_q") or 0
            result.append(seg)

    return sorted(result, key=lambda s: (s["q_number"] or 999, s["page_start"]))

"""
Theory answer evaluation engine.

Grading is based on two deterministic signals, both derived from the
*reference text actually used to generate the question* (the raw-data
chunk that was retrieved for that question, or an LLM-written model
answer distilled from that chunk):

1. Keyword coverage  - how many of the important terms found in the
   reference text also appear in the student's answer.
2. Semantic similarity - cosine similarity between sentence embeddings
   of the student's answer and the reference text.

No static per-subject keyword bank is used any more - keywords are
extracted on the fly from whatever reference text is supplied, so the
evaluator works for any subject/unit without manual curation.

An LLM (Ollama) can optionally be used to produce qualitative feedback
text, but it is NOT used to compute the score itself - the score is
always the deterministic keyword + semantic blend described above.
"""

import os
import json
import re
from typing import Optional
from pathlib import Path

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

# Generic stopwords filtered out before keyword extraction. Deliberately
# small/topic-agnostic so it works for any engineering subject.
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "with", "this",
    "that", "from", "have", "has", "had", "was", "were", "will", "would",
    "could", "should", "can", "their", "they", "them", "then", "than",
    "what", "when", "where", "which", "while", "about", "into", "such",
    "these", "those", "also", "each", "other", "some", "more", "most",
    "between", "being", "after", "before", "during", "over", "under",
    "above", "below", "because", "explain", "describe", "discuss",
    "define", "state", "derive", "calculate", "given", "using", "used",
    "use", "following", "based", "respect", "various", "different",
    "example", "examples", "question", "answer", "system", "value",
    "values", "case", "type", "types", "called", "known", "general",
}

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None and EMBEDDINGS_AVAILABLE:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def cosine_similarity(a, b) -> float:
    if not EMBEDDINGS_AVAILABLE:
        return 0.5
    import numpy as np
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

def extract_keywords(reference_text: str, top_n: int = 15) -> list:
    """
    Extracts the most important terms from a reference text (e.g. the raw
    source chunk a question was generated from, or its LLM-written model
    answer). Pure frequency + stopword filtering - no per-subject bank,
    so it generalizes to any topic.
    """
    if not reference_text:
        return []

    # Words, hyphenated terms, and possessive/apostrophe terms (e.g. "Bernoulli's")
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", reference_text)

    freq = {}
    for tok in tokens:
        lt = tok.lower().strip("-'")
        if len(lt) < 4 or lt in STOPWORDS:
            continue
        freq[lt] = freq.get(lt, 0) + 1

    # Rank by frequency, then prefer longer/more specific terms on ties
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    return [word for word, _ in ranked[:top_n]]


def keyword_coverage(student_text: str, reference_text: str, top_n: int = 15) -> dict:
    """
    Extracts keywords from `reference_text` (the raw-data-derived answer
    for the question) and checks how many appear in the student's answer.
    Returns found/missing keywords and a coverage ratio in [0, 1].
    """
    keywords = extract_keywords(reference_text, top_n=top_n)
    student_lower = student_text.lower()
    found = [k for k in keywords if k in student_lower]
    missing = [k for k in keywords if k not in found]
    return {
        "keywords_considered": keywords,
        "found": found,
        "missing": missing,
        "matched_count": len(found),
        "total_count": len(keywords),
        "coverage_ratio": len(found) / max(len(keywords), 1),
    }

def llm_feedback(question: str, reference_answer: str, student_answer: str,
                  kw: dict, similarity: float, subject: str = "",
                  model: str = None) -> str:
    """
    Optional: asks the LLM to write 2-3 sentences of qualitative feedback.
    This NEVER influences the score - it's purely explanatory text shown
    alongside the deterministic keyword/semantic score.
    """
    if not OLLAMA_AVAILABLE:
        return ""

    model = model or os.getenv("OLLAMA_MODEL", "mistral")
    prompt = f"""You are an expert {subject or 'engineering'} professor.
A student's theory answer was auto-graded by comparing it against the
source material the question was generated from.

QUESTION: {question}

REFERENCE MATERIAL / MODEL ANSWER (from the raw source data):
{reference_answer}

STUDENT ANSWER: {student_answer}

Matched keywords from the reference material: {', '.join(kw['found']) or 'none'}
Missing keywords from the reference material: {', '.join(kw['missing']) or 'none'}
Semantic similarity to reference: {similarity:.0%}

Write 2-3 sentences of specific, constructive feedback for the student
explaining what was covered well and what key terms/ideas were missing.
Respond with feedback text only, no JSON, no preamble."""

    try:
        resp = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3},
        )
        return resp["message"]["content"].strip()
    except Exception:
        return ""

def evaluate_theory(
    question: str,
    student_answer: str,
    reference_answer: str,
    subject: str = "",
    max_marks: int = 10,
    keyword_weight: float = 0.4,
    semantic_weight: float = 0.6,
    top_n_keywords: int = 15,
    skip_llm_feedback: bool = False,
) -> dict:
    """
    Main entry point for theory evaluation.

    `reference_answer` is the raw-data-derived answer for this question -
    i.e. the source chunk it was generated from, or an LLM-distilled model
    answer based on that chunk. Both keyword extraction AND semantic
    similarity are computed against this text, so a question generated
    from different source material is graded against different keywords
    automatically (no manual per-subject keyword bank needed).

    Score = keyword_weight * keyword_coverage_ratio
          + semantic_weight * semantic_similarity
      ...scaled to max_marks. Weights must sum to 1.0.

    `skip_llm_feedback`: when True, skips the llm_feedback() Ollama call and
    uses the deterministic fallback sentence instead. The score is computed
    identically either way (feedback never affects ai_score) - this is a
    free win for callers that only need scores in bulk (e.g. aggregating
    many submissions for dashboard stats) and would otherwise pay for an
    LLM call whose text output they immediately discard.

    Returns full evaluation result dict.
    """
    reference_answer = reference_answer or ""

    # 1. Keyword coverage against the reference (raw-data-derived) answer
    kw = keyword_coverage(student_answer, reference_answer, top_n=top_n_keywords)

    # 2. Semantic similarity against the same reference answer.
    # When sentence-transformers isn't installed at all, fall back to the
    # same neutral 0.5 that cosine_similarity() itself returns in that case
    # - previously this branch left `similarity` at its 0.0 initial value
    # instead, which silently zeroed out the entire 60%-weighted semantic
    # component of every score whenever embeddings were unavailable.
    similarity = 0.0
    if reference_answer and student_answer:
        if EMBEDDINGS_AVAILABLE:
            model_emb = get_embedding_model()
            if model_emb:
                vec_ref = model_emb.encode(reference_answer)
                vec_student = model_emb.encode(student_answer)
                similarity = cosine_similarity(vec_ref, vec_student)
            else:
                similarity = 0.5
        else:
            similarity = 0.5

    # 3. Deterministic blended score (keyword count + semantic match)
    blended = keyword_weight * kw["coverage_ratio"] + semantic_weight * similarity
    ai_score = round(blended * max_marks, 1)
    ai_score = max(0.0, min(ai_score, max_marks))

    # 4. Optional LLM-written feedback (does not affect ai_score)
    feedback = "" if skip_llm_feedback else llm_feedback(question, reference_answer, student_answer, kw, similarity, subject)
    if not feedback:
        feedback = (
            f"Matched {kw['matched_count']}/{kw['total_count']} key terms from the "
            f"source material ({kw['coverage_ratio']:.0%} keyword coverage). "
            f"Semantic similarity to the reference answer: {similarity:.0%}."
        )

    confidence = round(min(0.95, 0.5 + similarity * 0.3 + kw["coverage_ratio"] * 0.2), 2)

    keyword_marks = round(kw["coverage_ratio"] * keyword_weight * max_marks, 1)
    semantic_marks = round(similarity * semantic_weight * max_marks, 1)
    explanation = (
        f"Awarded {keyword_marks}/{round(keyword_weight * max_marks, 1)} marks for keyword coverage "
        f"({kw['matched_count']}/{kw['total_count']} key terms from the source material matched: "
        f"{', '.join(kw['found']) or 'none'}). "
        f"Awarded {semantic_marks}/{round(semantic_weight * max_marks, 1)} marks for semantic similarity "
        f"to the reference answer ({similarity:.0%} similarity). "
        f"Missing key terms: {', '.join(kw['missing']) or 'none'}. "
        f"Total: {ai_score}/{max_marks}."
    )

    return {
        "ai_score": ai_score,
        "max_score": max_marks,
        "keyword_score": round(kw["coverage_ratio"] * max_marks, 1),
        "semantic_score": round(similarity * max_marks, 1),
        "confidence": confidence,
        "feedback": feedback,
        "explanation": explanation,
        "keywords": kw,
        "similarity": round(similarity, 3),
    }

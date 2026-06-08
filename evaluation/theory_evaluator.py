"""
Theory answer evaluation engine.
Uses local LLM (Ollama) + cosine similarity + keyword coverage for two-tier scoring.
Concept score: is the core principle present?
Detail score: supporting reasoning + ME-specific terminology?
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

# ME domain keyword banks per subject
ME_KEYWORDS = {
    "Thermodynamics": [
        "entropy", "enthalpy", "isentropic", "adiabatic", "isothermal", "isobaric",
        "isochoric", "carnot", "rankine", "brayton", "otto", "diesel", "SFEE",
        "first law", "second law", "zeroth law", "heat transfer", "work done",
        "thermal efficiency", "COP", "refrigeration", "psychrometric", "dryness fraction",
        "superheated", "saturation", "latent heat", "specific heat", "Clausius",
        "reversible", "irreversible", "exergy", "availability", "T-s diagram", "p-V diagram",
    ],
    "Strength of Materials": [
        "stress", "strain", "Young's modulus", "Poisson's ratio", "shear force",
        "bending moment", "neutral axis", "moment of inertia", "section modulus",
        "deflection", "slope", "torsion", "polar moment", "principal stress",
        "Mohr's circle", "yield strength", "ultimate strength", "factor of safety",
        "buckling", "Euler", "slenderness ratio", "thin cylinder", "hoop stress",
        "longitudinal stress", "shear stress", "flexural formula", "Castigliano",
    ],
    "Fluid Mechanics": [
        "Reynolds number", "Bernoulli", "continuity equation", "viscosity",
        "laminar", "turbulent", "boundary layer", "Navier-Stokes", "pressure drop",
        "Darcy-Weisbach", "Moody diagram", "pipe flow", "open channel",
        "hydraulic gradient", "specific gravity", "surface tension", "capillarity",
        "venturimeter", "orifice", "pitot tube", "notch", "weir", "buoyancy",
        "metacentre", "vortex", "circulation", "lift", "drag",
    ],
    "Engineering Drawing": [
        "orthographic", "isometric", "first angle", "third angle", "auxiliary view",
        "section", "cutting plane", "hatching", "hidden line", "centre line",
        "dimension", "tolerance", "GD&T", "datum", "surface finish", "Ra",
        "title block", "scale", "projection", "elevation", "plan", "side view",
        "true shape", "development", "intersection",
    ],
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

def keyword_coverage(student_text: str, subject: str) -> dict:
    """Returns dict of found/missing keywords and coverage ratio."""
    keywords = ME_KEYWORDS.get(subject, [])
    student_lower = student_text.lower()
    found = [k for k in keywords if k.lower() in student_lower]
    missing = [k for k in keywords if k.lower() not in student_lower]
    return {
        "found": found[:15],  # top 15
        "missing": missing[:10],
        "coverage_ratio": len(found) / max(len(keywords), 1),
    }

def llm_evaluate(question: str, model_answer: str, student_answer: str,
                 subject: str, model: str = None) -> dict:
    """
    Uses LLM to evaluate student answer against model answer.
    Returns concept_score (0-5), detail_score (0-5), and feedback.
    """
    if not OLLAMA_AVAILABLE:
        return {"concept_score": 0, "detail_score": 0, "feedback": "LLM not available"}

    model = model or os.getenv("OLLAMA_MODEL", "mistral")
    prompt = f"""You are an expert {subject} professor grading a student answer.

QUESTION: {question}

MODEL ANSWER: {model_answer}

STUDENT ANSWER: {student_answer}

Evaluate the student answer on TWO criteria (0-5 each):
1. CONCEPT SCORE (0-5): Is the core principle/concept correctly stated and understood?
   - 5: Perfect understanding, all key concepts present
   - 3-4: Core concept present, minor gaps
   - 1-2: Partial understanding, significant gaps
   - 0: Core concept absent or wrong

2. DETAIL SCORE (0-5): Quality of reasoning, supporting details, correct ME terminology?
   - 5: Excellent supporting reasoning, all steps/derivations correct, proper terminology
   - 3-4: Good reasoning with minor omissions
   - 1-2: Superficial reasoning, missing important steps
   - 0: No meaningful supporting detail

Respond ONLY in this exact JSON format:
{{"concept_score": <0-5>, "detail_score": <0-5>, "feedback": "<2-3 sentences of specific feedback>"}}"""

    try:
        resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        text = resp["message"]["content"].strip()
        # Extract JSON
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"concept_score": 0, "detail_score": 0, "feedback": "Evaluation failed — LLM error"}

def evaluate_theory(
    question: str,
    student_answer: str,
    subject: str,
    model_answer: str = "",
    max_marks: int = 10,
) -> dict:
    """
    Main entry point for theory evaluation.
    Returns full evaluation result dict.
    """
    # Keyword analysis
    kw = keyword_coverage(student_answer, subject)

    # Cosine similarity (if model answer provided)
    similarity = 0.5
    if model_answer and EMBEDDINGS_AVAILABLE:
        model_emb = get_embedding_model()
        if model_emb:
            vec_model = model_emb.encode(model_answer)
            vec_student = model_emb.encode(student_answer)
            similarity = cosine_similarity(vec_model, vec_student)

    # LLM scoring
    llm_result = llm_evaluate(question, model_answer or question, student_answer, subject)
    concept_score = llm_result.get("concept_score", 0)
    detail_score = llm_result.get("detail_score", 0)
    feedback = llm_result.get("feedback", "")

    # If LLM unavailable, estimate from keyword coverage + similarity
    if not OLLAMA_AVAILABLE:
        concept_score = round(kw["coverage_ratio"] * 5, 1)
        detail_score = round(similarity * 5, 1)
        feedback = (
            f"Keyword coverage: {len(kw['found'])} terms found. "
            f"Semantic similarity to model answer: {similarity:.0%}."
        )

    # Final score out of max_marks
    raw_total = concept_score + detail_score  # 0-10
    ai_score = round((raw_total / 10) * max_marks, 1)
    confidence = min(0.95, 0.5 + similarity * 0.3 + kw["coverage_ratio"] * 0.2)

    return {
        "ai_score": ai_score,
        "max_score": max_marks,
        "concept_score": concept_score,
        "detail_score": detail_score,
        "confidence": round(confidence, 2),
        "feedback": feedback,
        "keywords": kw,
        "similarity": round(similarity, 3),
    }

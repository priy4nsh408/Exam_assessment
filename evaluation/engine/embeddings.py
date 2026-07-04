"""
Embedding layer — semantic similarity used for:
  • matching un-numbered answers to answer-scheme questions
  • matching shuffled answers (Q5, Q1, Q8 order) to the right question
  • theory fallback grading

Uses sentence-transformers all-MiniLM-L6-v2 (local, fast, no API needed).
Falls back to token-overlap Jaccard if the model isn't installed.
"""

from __future__ import annotations
import re
from typing import List

_model = None
_model_failed = False


def _get_model():
    global _model, _model_failed
    if _model is None and not _model_failed:
        try:
            from sentence_transformers import SentenceTransformer
            from evaluation.engine.config import get_config
            _model = SentenceTransformer(get_config().embedding_model)
        except Exception:
            _model_failed = True
    return _model


def _jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z]{3,}", a.lower()))
    tb = set(re.findall(r"[a-z]{3,}", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def similarity(a: str, b: str) -> float:
    """Cosine similarity between two texts, 0..1."""
    model = _get_model()
    if model is None:
        return _jaccard(a, b)
    try:
        import numpy as np
        va, vb = model.encode([a[:2000], b[:2000]])
        sim = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))
        return max(0.0, min(1.0, sim))
    except Exception:
        return _jaccard(a, b)


def similarity_matrix(texts_a: List[str], texts_b: List[str]) -> List[List[float]]:
    """Pairwise cosine similarities between two lists of texts."""
    model = _get_model()
    if model is None:
        return [[_jaccard(a, b) for b in texts_b] for a in texts_a]
    try:
        import numpy as np
        va = model.encode([t[:2000] for t in texts_a])
        vb = model.encode([t[:2000] for t in texts_b])
        va = va / (np.linalg.norm(va, axis=1, keepdims=True) + 1e-9)
        vb = vb / (np.linalg.norm(vb, axis=1, keepdims=True) + 1e-9)
        return np.clip(va @ vb.T, 0.0, 1.0).tolist()
    except Exception:
        return [[_jaccard(a, b) for b in texts_b] for a in texts_a]

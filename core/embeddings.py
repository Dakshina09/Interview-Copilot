"""
Local text embeddings via fastembed (ONNX, no PyTorch -- keeps Streamlit Cloud builds light).

Groq has no embeddings endpoint, so this runs on-device. If the model can't be
downloaded (offline / blocked network) we fall back to character n-gram TF-IDF so the
app still works -- `backend_name()` tells the UI which one is active.
"""

from __future__ import annotations
import re
from functools import lru_cache
import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_backend = None   # "fastembed" | "lexical"


@lru_cache(maxsize=1)
def _load_model():
    global _backend
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(MODEL_NAME)
        _backend = "fastembed"
        return model
    except Exception:
        _backend = "lexical"
        return None


def backend_name() -> str:
    _load_model()
    return _backend


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def _ngrams(text: str, n: int = 3) -> list[str]:
    t = f" {re.sub(r'[^a-z0-9+#]+', ' ', text.lower()).strip()} "
    return [t[i:i + n] for i in range(max(len(t) - n + 1, 1))]


def _lexical_embed(texts: list[str], vocab_texts: list[str]) -> np.ndarray:
    vocab = {g: i for i, g in enumerate(sorted({g for t in vocab_texts for g in _ngrams(t)}))}
    m = np.zeros((len(texts), len(vocab)), dtype=np.float32)
    for r, t in enumerate(texts):
        for g in _ngrams(t):
            if g in vocab:
                m[r, vocab[g]] += 1
    return _normalize(m)


def similarity_matrix(queries: list[str], docs: list[str]) -> np.ndarray:
    """Cosine similarity, shape (len(queries), len(docs))."""
    if not queries or not docs:
        return np.zeros((len(queries), len(docs)))
    model = _load_model()
    if model is None:
        allt = queries + docs
        return _lexical_embed(queries, allt) @ _lexical_embed(docs, allt).T
    q = _normalize(np.array(list(model.embed(queries))))
    d = _normalize(np.array(list(model.embed(docs))))
    return q @ d.T

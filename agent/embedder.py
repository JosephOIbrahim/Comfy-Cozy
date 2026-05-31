"""BGE embedder for cognitive memory retrieval.

Lazy-loaded `BAAI/bge-small-en-v1.5` model produces 384-dimension
L2-normalized vectors for semantic similarity search.

The model is downloaded from HuggingFace on first call (~130MB cache
at `~/.cache/huggingface/hub/`) and held in process for subsequent
calls. Used for symmetric text-similarity (no query prefix); the
asymmetric query/passage prefix is a future consumer concern.

This module exposes the embedder API only — it does NOT touch the
existing `record_outcome` path or the comfy-moneta-bridge JSONL
pipeline. Those continue to operate untouched. The in-process Moneta
migration that consumes this embedder is a later locked-decision step.

Public API:
    embed(payload: str) -> list[float]   # 384-dim, L2-normalized
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

_model: "SentenceTransformer | None" = None
_model_lock = threading.Lock()


def _load_model() -> "SentenceTransformer":
    """Load (or return the cached) SentenceTransformer instance.

    Thread-safe via double-checked locking. The SDK import is also
    deferred to here so the agent package stays importable on machines
    that haven't installed the embedder extras yet.
    """
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Semantic embeddings need the 'embed' extra — install with "
                "`pip install -e \".[embed]\"` (pulls sentence-transformers + torch)."
            ) from exc
        _model = SentenceTransformer(_MODEL_NAME)
        return _model


def embed(payload: str) -> list[float]:
    """Encode `payload` as a 384-dim L2-normalized embedding.

    Args:
        payload: Text to embed. Must be a string; empty strings are
            allowed and produce the model's special-token-only vector.

    Returns:
        A list of `EMBED_DIM` (384) float values. L2-normalized, so
        cosine similarity equals the dot product.

    Raises:
        TypeError: payload is not a string.
    """
    if not isinstance(payload, str):
        raise TypeError(f"embed() requires str, got {type(payload).__name__}")
    model = _load_model()
    vec = model.encode(payload, normalize_embeddings=True)
    return vec.tolist()


def _reset_for_tests() -> None:
    """Test-only: drop the cached model so the next embed() reloads."""
    global _model
    with _model_lock:
        _model = None

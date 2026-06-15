"""Vector Embedding Engine — generate embeddings for semantic memory search.

Primary: ONNX Runtime with a small ONNX embedding model (all-MiniLM-L6-v2,
384-dimensional).  If onnxruntime is not installed, falls back to a
zero-dependency character n-gram hash embedding that still provides
meaningful similarity ordering for short-to-medium text.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── ONNX availability ────────────────────────────────────────────────

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    ort = None
    HAS_ONNX = False

# ── Helpers ──────────────────────────────────────────────────────────

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALPHA_RE = re.compile(r"[^a-z0-9\s]")
_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, Any] = {}


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _WHITESPACE_RE.sub(" ", _NON_ALPHA_RE.sub(" ", text.lower())).strip()


# ═══════════════════════════════════════════════════════════════════════
# Embedding engine
# ═══════════════════════════════════════════════════════════════════════


class EmbeddingEngine:
    """Generate vector embeddings from text.

    Modes (tried in order):
    1. **onnx** — ONNX Runtime with a tiny BERT-like model.
       Downloads to ``model_dir`` on first use.
    2. **ngram** — Zero-dependency character n-gram hash embedding.

    Produces **384-dimensional** vectors in all modes so the downstream
    storage layout is always the same.
    """

    DIMENSIONS = 384
    ONNX_MODEL_REPO = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx"

    def __init__(self, model_dir: str | Path | None = None):
        self._model_dir = Path(model_dir) if model_dir else Path.home() / ".nexus-agent" / "models" / "embeddings"
        self._model_dir.mkdir(parents=True, exist_ok=True)

        self._mode: str = "ngram"  # fallback default
        self._session: Any = None
        self._tokenizer: Any = None
        self._tokenizer_json: dict[str, Any] | None = None
        self._lock = threading.Lock()

        # Try ONNX first
        self._try_init_onnx()

        if self._mode == "ngram":
            logger.info("EmbeddingEngine: using ngram fallback (384d)")

    # ── ONNX initialisation ──────────────────────────────────────────

    def _try_init_onnx(self) -> None:
        """Attempt to initialise the ONNX Runtime embedding model."""
        if not HAS_ONNX:
            return
        if not HAS_NUMPY:
            return

        model_path = self._model_dir / "model.onnx"
        tokenizer_path = self._model_dir / "tokenizer.json"

        if not model_path.exists() or not tokenizer_path.exists():
            logger.info(
                "ONNX embedding model not found at %s — "
                "run download_model() or use the ngram fallback.",
                self._model_dir,
            )
            return

        try:
            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(
                str(model_path), so, providers=["CPUExecutionProvider"],
            )
            with open(tokenizer_path, encoding="utf-8") as f:
                self._tokenizer_json = json.load(f)
            self._mode = "onnx"
            logger.info("EmbeddingEngine: ONNX mode ready (%s)", model_path.name)
        except Exception as exc:
            logger.warning("EmbeddingEngine: ONNX init failed (%s)", exc)
            self._session = None
            self._tokenizer_json = None

    def download_model(self, force: bool = False) -> bool:
        """Download the ONNX embedding model from Hugging Face.

        Returns ``True`` if the model is available after the call
        (either already cached or freshly downloaded).
        """
        if self._mode == "onnx" and not force:
            return True

        model_path = self._model_dir / "model.onnx"
        tokenizer_path = self._model_dir / "tokenizer.json"

        if model_path.exists() and tokenizer_path.exists() and not force:
            self._try_init_onnx()
            return self._mode == "onnx"

        import httpx

        files = {
            "model.onnx": model_path,
            "tokenizer.json": tokenizer_path,
        }

        for fname, dest in files.items():
            url = f"{self.ONNX_MODEL_REPO}/{fname}"
            logger.info("Downloading %s …", url)
            try:
                resp = httpx.get(url, follow_redirects=True, timeout=120)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
            except Exception as exc:
                logger.error("Failed to download %s: %s", url, exc)
                return False

        self._try_init_onnx()
        return self._mode == "onnx"

    # ── Public API ───────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        """Produce a 384-dimensional embedding vector for *text*.

        The result is a flat Python list of floats suitable for
        serialisation (e.g. JSON or ``struct.pack``).
        """
        if not text or not text.strip():
            return [0.0] * self.DIMENSIONS

        with self._lock:
            if self._mode == "onnx":
                return self._embed_onnx(text)
            return self._embed_ngram(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed multiple texts."""
        return [self.embed(t) for t in texts]

    @property
    def mode(self) -> str:
        """Active engine mode: ``"onnx"`` or ``"ngram"``."""
        return self._mode

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS

    # ── ONNX embedding ───────────────────────────────────────────────

    def _embed_onnx(self, text: str) -> list[float]:
        """Embed using the ONNX model."""
        if self._session is None or self._tokenizer_json is None:
            # Fall back to ngram if ONNX not actually ready
            return self._embed_ngram(text)

        try:
            tokens = self._tokenize_onnx(text)
            input_ids = np.array([tokens["input_ids"]], dtype=np.int64)
            attention_mask = np.array([tokens["attention_mask"]], dtype=np.int64)
            token_type_ids = np.array([tokens.get("token_type_ids", [0] * len(tokens["input_ids"]))], dtype=np.int64)

            result = self._session.run(
                None,
                {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "token_type_ids": token_type_ids,
                },
            )
            # Mean-pool the last hidden state
            embeddings = result[0]  # shape (1, seq_len, 384)
            mask = attention_mask[0][:, np.newaxis].astype(np.float32)  # (seq_len, 1)
            masked = embeddings[0] * mask
            summed = masked.sum(axis=0)
            lengths = mask.sum(axis=0)
            lengths = np.maximum(lengths, 1e-9)
            pooled = summed / lengths

            # L2 normalise
            norm = np.linalg.norm(pooled)
            if norm > 0:
                pooled = pooled / norm

            return pooled.tolist()
        except Exception as exc:
            logger.warning("ONNX embedding failed, falling back to ngram: %s", exc)
            return self._embed_ngram(text)

    def _tokenize_onnx(self, text: str) -> dict[str, list[int]]:
        """Simple BERT tokenizer (WordPiece) using the tokenizer.json.

        This is a simplified tokenizer that handles the common case.
        For production use, the ``tokenizers`` package would be better,
        but we avoid the dependency here.
        """
        # Build lookup from the tokenizer JSON
        if self._tokenizer_json is None:
            return {"input_ids": [0, 0], "attention_mask": [1, 1]}

        max_len = 128
        vocab = self._tokenizer_json.get("model", {}).get("vocab", {})

        def tokenize_word(word: str) -> list[int]:
            """Simple WordPiece tokenization."""
            if word in vocab:
                return [vocab[word]]
            ids = []
            # Try sub-word splitting
            for i in range(len(word)):
                for j in range(len(word), i, -1):
                    sub = word[i:j]
                    if i > 0:
                        sub = "##" + sub
                    if sub in vocab:
                        ids.append(vocab[sub])
                        i = j
                        break
            if not ids:
                ids = [vocab.get("[UNK]", 100)]
            return ids

        tokens = ["[CLS]"]
        for word in _normalize(text).split()[:max_len - 2]:
            tokens.append(word)
        tokens.append("[SEP]")

        input_ids = []
        for token in tokens[:max_len]:
            if token in vocab:
                input_ids.append(vocab[token])
            elif token == "[CLS]":
                input_ids.append(vocab.get("[CLS]", 101))
            elif token == "[SEP]":
                input_ids.append(vocab.get("[SEP]", 102))
            else:
                input_ids.append(vocab.get("[UNK]", 100))

        # Pad to max_len
        pad_id = vocab.get("[PAD]", 0)
        orig_len = len(input_ids)
        input_ids = input_ids[:max_len] + [pad_id] * (max_len - len(input_ids))
        attention_mask = [1] * min(orig_len, max_len) + [0] * (max_len - min(orig_len, max_len))

        return {"input_ids": input_ids, "attention_mask": attention_mask}

    # ── Ngram fallback embedding ─────────────────────────────────────

    def _embed_ngram(self, text: str) -> list[float]:
        """Zero-dependency character n-gram hash embedding.

        Produces a fixed 384-dimensional vector by hashing character
        2-grams and 3-grams into bins and computing a TF-like score.
        This is *not* as accurate as a neural model but captures
        character-level similarity meaningfully for short-to-medium
        text.
        """
        vec = [0.0] * self.DIMENSIONS
        text = _normalize(text)
        if not text:
            return vec

        ngrams: list[str] = []
        # 2-grams
        for i in range(len(text) - 1):
            ngrams.append(text[i:i + 2])
        # 3-grams
        for i in range(len(text) - 2):
            ngrams.append(text[i:i + 3])

        if not ngrams:
            return vec

        # Hash each ngram into a bin position and accumulate
        for ng in ngrams:
            h = int(hashlib.md5(ng.encode()).hexdigest()[:8], 16)
            idx = h % self.DIMENSIONS
            vec[idx] += 1.0

        # Length normalise
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec


# ═══════════════════════════════════════════════════════════════════════
# Convenience
# ═══════════════════════════════════════════════════════════════════════

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors.

    Performance optimized: Uses a single loop instead of multiple
    generator expressions to avoid overhead in the linear scan loop.
    """
    if len(a) != len(b):
        return 0.0

    dot = 0.0
    na2 = 0.0
    nb2 = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na2 += x * x
        nb2 += y * y

    if na2 < 1e-24 or nb2 < 1e-24:
        return 0.0
    return dot / math.sqrt(na2 * nb2)

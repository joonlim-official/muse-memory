"""Lightweight semantic embedding layer for muse-memory ContextGraph (stdlib only).

Supports two backends:
  - `gemini`: Google Gemini Embedding API (paid Tier 1, `GEMINI_API_KEY`), ideal for
    conceptual queries where lexical/alias/FTS5 search returns zero hits.
  - `local`:  Zero-dependency deterministic hashed word + char-trigram vector (256-dim),
    for offline Mac mini use and unit tests.

Vectors are cached in SQLite (`node_embeddings`) keyed by content SHA-256 so unchanged
nodes are never re-embedded.
"""

import array
import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request

LOCAL_DIMS = 256
TOKEN_RE = re.compile(r"[a-z0-9]+")
DEFAULT_GEMINI_MODEL = "text-embedding-004"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def pack_vector(vec: list[float]) -> bytes:
    return array.array("f", vec).tobytes()


def unpack_vector(blob: bytes) -> list[float]:
    arr = array.array("f")
    arr.frombytes(blob)
    return list(arr)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def embed_local(text: str, dims: int = LOCAL_DIMS) -> list[float]:
    """Deterministic hashed word + character-trigram TF vector (L2-normalized)."""
    vec = [0.0] * dims
    tokens = TOKEN_RE.findall(text.lower())
    for tok in tokens:
        if len(tok) < 2:
            continue
        # Word feature (higher weight)
        h = int(hashlib.blake2b(f"w:{tok}".encode("utf-8"), digest_size=4).hexdigest(), 16)
        vec[h % dims] += 2.0
        # Character trigrams (fuzzy / morphological similarity)
        padded = f"^{tok}$"
        for i in range(len(padded) - 2):
            tri = padded[i : i + 3]
            ht = int(hashlib.blake2b(f"t:{tri}".encode("utf-8"), digest_size=4).hexdigest(), 16)
            vec[ht % dims] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0.0 else vec


def embed_gemini(text: str, api_key: str, model: str = DEFAULT_GEMINI_MODEL, timeout: int = 20) -> list[float]:
    """Call Gemini Embedding REST API using Python stdlib urllib."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}"
    payload = json.dumps({"content": {"parts": [{"text": text[:4000]}]}}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini embedding API call failed: {exc}") from exc
    values = (data.get("embedding") or {}).get("values")
    if not isinstance(values, list) or not values:
        raise RuntimeError("Gemini embedding API returned empty vector")
    return [float(x) for x in values]


def choose_backend(requested: str = "auto") -> str:
    if requested in ("gemini", "local"):
        if requested == "gemini" and not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not set for --backend gemini")
        return requested
    return "gemini" if os.environ.get("GEMINI_API_KEY") else "local"


def embed_text(text: str, backend: str = "auto", model: str = DEFAULT_GEMINI_MODEL) -> tuple[list[float], str]:
    chosen = choose_backend(backend)
    if chosen == "gemini":
        key = os.environ["GEMINI_API_KEY"]
        return embed_gemini(text, key, model=model), f"gemini:{model}"
    return embed_local(text), f"local:ngram-{LOCAL_DIMS}"

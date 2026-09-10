"""Semantic retrieval layer (genesis Part XXI).

Builds a vector embedding store from every supported document in input/context/
(the shared text_extract format family: .pdf/.docx/.html/.htm/.txt/.md/.rst/
.log/.json) and provides cosine-similarity retrieval for context assembly. The
store is part of the snapshot and persists across runs via save/load.

Graceful degradation: if sentence-transformers is not installed, or if
the model fails to load, every function in this module returns a safe
fallback (0 passages built, None on load, [] on query) and the pipeline
silently uses Zipfian filtering instead.

Chunking: ~400-character passages, small enough to sit well under the bge-m3
8192-token context window, large enough to carry one or two sentences of
meaningful content per chunk.
"""

from __future__ import annotations

import reference_builder
import hashlib
import json
import pickle
import re
import sys
import time
from pathlib import Path
from typing import Any

import language_detect
import text_extract


# Single multilingual model for ALL languages (BAAI/bge-m3): 100+ languages incl.
# Arabic/Hebrew, 1024-dim, 8192-token context, strong on English too. One shared
# embedding space means TRUE cross-language retrieval: an English query can score
# against Arabic passages because they live in the same space (the old per-language
# split embedded English and non-English with different models, so a query only ever
# matched within its own model's sub-store). Downloaded by sentence-transformers at
# runtime (~2.3 GB); if unavailable, _resolve_model() degrades gracefully.
DEFAULT_MODEL_NAME = "BAAI/bge-m3"
# Kept as a named constant for the resolve/fallback chain; same model now, so every
# language resolves to one shared cross-language space.
MULTILINGUAL_DEFAULT_MODEL = "BAAI/bge-m3"
# Language (ISO 639-1) -> embedding model. With one multilingual model this maps
# everything to bge-m3; extensible if a language-specialized model is ever clearly
# better (a different model would re-split that language into its own sub-store).
LANG_MODEL_REGISTRY = {
    "en": DEFAULT_MODEL_NAME,
}
CHUNK_TARGET_CHARS = 400
CHUNK_OVERLAP_CHARS = 80

# Loaded SentenceTransformer instances, keyed by model id (avoid reloading).
_MODEL_CACHE: dict = {}


def model_for_language(lang: str) -> str:
    """Map a document's dominant language to its embedding model. English and
    unknown ('und' / unset, e.g. when langdetect is absent) keep the fast
    English default so detection-off never triggers a surprise model download;
    only a positively-detected non-English language switches to multilingual."""
    code = (lang or "").lower()
    if code in ("", "und"):
        return DEFAULT_MODEL_NAME
    return LANG_MODEL_REGISTRY.get(code, MULTILINGUAL_DEFAULT_MODEL)


def _registry_signature() -> str:
    """Stable hash of the language->model policy. Recorded in the store so a
    change to the registry (different models) forces a rebuild; staleness
    accounts for the model used, not just the document set."""
    # "v" is bumped whenever the passage SHAPE changes, not only the model: v4 = the
    # table-aware chunker (a store built with v3 holds tables flattened into single
    # lines, cut mid-row, headers detached; it must be rebuilt, not reused).
    payload = json.dumps(
        {"registry": LANG_MODEL_REGISTRY, "default": MULTILINGUAL_DEFAULT_MODEL,
         "english": DEFAULT_MODEL_NAME, "v": 4},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _embed_device() -> str:
    """The device to encode on: 'cuda' when a GPU is present, else 'cpu'. Explicit
    so encoding always uses the GPU when available (bge-m3 is large; CPU encoding is
    far slower). Exception: when SHIMMER_BACKEND_PROFILE=local, the generation model
    needs the full GPU, so bge-m3 runs on CPU to avoid VRAM contention. torch is a
    sentence-transformers dependency, so the import is safe on the path that loads a
    model; any failure degrades to CPU."""
    import os
    if os.environ.get("SHIMMER_BACKEND_PROFILE") == "local":
        return "cpu"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _ensure_safetensors(name):
    """Materialize a local model.safetensors from a model's cached pytorch_model.bin,
    ONCE, and return the local snapshot dir (or None on failure).

    Why: torch < 2.6 + transformers refuse to load pickle (.bin) weights via
    torch.load (CVE-2025-32434), and some models (e.g. BAAI/bge-m3) publish ONLY
    .bin. Converting to safetensors uses the allowed, safe loading path. Idempotent:
    if safetensors already exist (here or upstream), just return the dir. After this
    runs once, even the normal SentenceTransformer(name) load finds the safetensors.
    Writes into the HF cache snapshot, never the repo. Degrades to None on any error
    (the caller then reports the model unavailable and the pipeline uses Zipfian)."""
    try:
        from huggingface_hub import snapshot_download
        from safetensors.torch import save_file
        import torch
    except Exception:
        return None
    try:
        snap = Path(snapshot_download(name))
    except Exception:
        return None
    if (snap / "model.safetensors").exists() or (snap / "model.safetensors.index.json").exists():
        return str(snap)
    bin_path = snap / "pytorch_model.bin"
    if not bin_path.exists():
        return None
    try:
        sd = torch.load(str(bin_path), map_location="cpu", weights_only=False)
        if isinstance(sd, dict) and "state_dict" in sd:
            sd = sd["state_dict"]
        sd = {k: v.contiguous() for k, v in sd.items() if hasattr(v, "contiguous")}
        save_file(sd, str(snap / "model.safetensors"), metadata={"format": "pt"})
        print(f"[embedding_store] materialized safetensors for {name!r} (torch<2.6 .bin "
              f"workaround)", file=sys.stderr, flush=True)
        return str(snap)
    except Exception as e:
        print(f"[embedding_store] safetensors conversion failed for {name!r} "
              f"({type(e).__name__}: {e})", file=sys.stderr, flush=True)
        return None


def _load_model(st, name):
    """Load (and cache) a SentenceTransformer by id, pinned to the GPU when present.
    Returns None on failure. On the torch<2.6 pickle-weights block, falls back to a
    one-time safetensors materialization (see _ensure_safetensors) and retries.

    Tries local_files_only=True FIRST, network-permitted only as the fallback:
    unlike the generation models (server.py's own pre-run check already resolves
    those with local_files_only=True and refuses to start a run if they are not
    cached), nothing checks this model's cache before a run starts, and the
    README documents "fetched at first use" as the real, intended behavior for a
    genuinely first run. Forcing local_files_only=True unconditionally would
    break that documented case. Trying it first means the COMMON case, an
    already-cached model on every run after the first, never touches the network
    at all (found live: agent_wrapper.py's generation-model loader was reaching
    the hub on every call despite being cached, and a routine network hiccup
    turned that into a fatal error; this function has the same structural gap,
    just with a softer failure mode today because it already tolerates a load
    failure). Falling back to the network-permitted path on a genuine cache miss
    preserves the exact behavior a first run has always had."""
    if name in _MODEL_CACHE:
        return _MODEL_CACHE[name]
    device = _embed_device()
    model = None
    try:
        model = st.SentenceTransformer(name, device=device, local_files_only=True)
    except Exception:
        try:
            model = st.SentenceTransformer(name, device=device)
        except Exception as e:
            local = _ensure_safetensors(name)
            if local is not None:
                try:
                    model = st.SentenceTransformer(local, device=device,
                                                   model_kwargs={"use_safetensors": True})
                except Exception as e2:
                    print(f"[embedding_store] WARN: model {name!r} unavailable after safetensors "
                          f"fallback ({type(e2).__name__}: {e2})", file=sys.stderr, flush=True)
            else:
                print(f"[embedding_store] WARN: model {name!r} unavailable "
                      f"({type(e).__name__}: {e})", file=sys.stderr, flush=True)
    if model is not None:
        # Observability: log the model, its actual device, and embedding dimension,
        # so every run shows the retrieval model loaded on the GPU (or CPU) and at
        # what dimension (mirrors the BP-6 Qwen device log).
        try:
            dim = model.get_sentence_embedding_dimension()
            dev = next(model._first_module().parameters()).device
            print(f"[embedding_store] model {name!r} loaded on {dev} (dim={dim})",
                  file=sys.stderr, flush=True)
        except Exception:
            pass
    _MODEL_CACHE[name] = model
    return model


def _resolve_model(st, name):
    """Return (actual_name, model), degrading gracefully: requested model ->
    multilingual default -> English default. (actual_name, None) only if none
    load. Never silently mislabels: the returned name is what actually embedded."""
    tried = []
    for candidate in (name, MULTILINGUAL_DEFAULT_MODEL, DEFAULT_MODEL_NAME):
        if candidate in tried:
            continue
        tried.append(candidate)
        model = _load_model(st, candidate)
        if model is not None:
            if candidate != name:
                print(f"[embedding_store] WARN: falling back from {name!r} to "
                      f"{candidate!r}", file=sys.stderr, flush=True)
            return candidate, model
    return None, None


def _try_import_st():
    try:
        import sentence_transformers
        return sentence_transformers
    except ImportError:
        return None


def _try_import_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None


# A markdown table row: a line that starts and ends with a pipe. The separator row
# (|---|---|) is matched separately so it can be kept with the header.
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")


def _split_tables(text: str) -> list:
    """Split a page into alternating ("prose", str) and ("table", [rows]) segments.
    A table is a maximal run of consecutive lines matching _TABLE_ROW_RE. Everything
    else, blank lines included, is prose in original order."""
    segments = []
    prose_lines: list[str] = []
    table_rows: list[str] = []

    def flush_prose():
        if prose_lines:
            segments.append(("prose", "\n".join(prose_lines)))
            prose_lines.clear()

    def flush_table():
        if table_rows:
            segments.append(("table", list(table_rows)))
            table_rows.clear()

    for line in text.splitlines():
        if _TABLE_ROW_RE.match(line):
            flush_prose()
            table_rows.append(" ".join(line.split()))
        else:
            flush_table()
            prose_lines.append(line)
    flush_prose()
    flush_table()
    return segments


def _chunk_table_rows(rows: list, target: int) -> list[str]:
    """Chunk a markdown table ROW-WISE. A row is never split. Every chunk that carries
    data rows starts with the header row (and its |---| separator when present), so a
    row is never separated from the column names that give its numbers meaning. A
    single very long row still becomes its own (header-carrying) chunk rather than
    being cut."""
    if not rows:
        return []
    head = [rows[0]]
    data = rows[1:]
    if data and _TABLE_SEP_RE.match(data[0]):
        head.append(data[0])
        data = data[1:]
    head_text = "\n".join(head)
    if not data:
        return [head_text]
    chunks = []
    current: list[str] = []
    for row in data:
        candidate_len = len(head_text) + sum(len(r) + 1 for r in current) + len(row) + 1
        if current and candidate_len > target:
            chunks.append("\n".join(head + current))
            current = []
        current.append(row)
    if current:
        chunks.append("\n".join(head + current))
    return chunks


def _chunk_prose(text: str, *, target: int = CHUNK_TARGET_CHARS,
                 overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """The original chunker, unchanged: collapse whitespace, then ~target-char
    chunks with small overlap, preferring sentence/paragraph boundaries. Used for
    everything that is not a markdown table, so tableless documents chunk
    byte-identically to before the table-aware split existed."""
    if not text:
        return []
    text = " ".join(text.split())  # collapse whitespace
    if not text:
        return []
    if len(text) <= target:
        return [text]
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + target)
        if end < n:
            # nudge end to the next sentence boundary or space within a small window
            for boundary in (". ", "? ", "! ", ".\n", "\n"):
                idx = text.find(boundary, end - 60, end + 60)
                if idx != -1:
                    end = idx + len(boundary)
                    break
            else:
                space = text.rfind(" ", end - 40, end)
                if space != -1:
                    end = space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _chunk_page(text: str, *, target: int = CHUNK_TARGET_CHARS,
                overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split text into ~target-char passages.

    Markdown tables are chunked ROW-WISE (the wheat-run fix): a table row is never
    split, and every chunk carrying table rows starts with that table's header row
    (plus its |---| separator), so a row is never separated from the column names
    that give its numbers meaning. Prose between tables goes through _chunk_prose,
    the original algorithm, unchanged, so a document with no tables chunks
    byte-identically to before.

    Before this, the whole page went through " ".join(text.split()), which merged
    every table row into one line, and fixed ~400-char boundaries then cut tables
    mid-row and left the header in a different passage from its data. Confirmed on
    the real reference corpus: a retrieved yield-band passage reached the agent as a
    headerless fragment ("...ral Anatolia, dryland | 2.4 | 1.6 to 3.4 | ...") with
    the word "Central" itself split and no column names anywhere in it. No model can
    compare a yield to a band from that. This runs identically on every backend
    profile (build_store has no profile check), so the cloud path had the same defect
    and gets the same fix."""
    if not text:
        return []
    chunks: list[str] = []
    for kind, payload in _split_tables(text):
        if kind == "table":
            chunks.extend(_chunk_table_rows(payload, target))
        else:
            chunks.extend(_chunk_prose(payload, target=target, overlap=overlap))
    return chunks


def build_store(
    context_dir: Path,
    store_path: Path,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    reference_index: Any = None,
) -> int:
    """Build an embedding store from every supported document in context_dir
    (the shared text_extract format family), OR load an existing one if the
    corpus hasn't changed.

    Staleness rule: if a pickle exists at `store_path`, compare the set of
    supported document filenames in context_dir against the set of doc_names
    recorded in the store's passages. If they match, the existing store is reused and
    we return its passage count without rebuilding. If they differ (any
    add or remove), the store is rebuilt from scratch.

    If `reference_index` is provided, each passage is also registered
    with the index via `reference_index.add(...)` so REF-* identifiers
    are shared between the Zipfian and semantic retrieval paths. If not
    provided, the store mints local ref_ids and the caller is responsible
    for any cross-walk it needs.

    Returns the number of passages in the active store (loaded or built).
    Returns 0 on graceful degradation (missing library, model load failure,
    no supported documents found).
    """
    # Staleness check: load existing pickle if present, compare to corpus.
    if store_path.exists():
        existing = load_store(store_path)
        stale, _added, _removed = is_store_stale(existing, context_dir)
        if not stale and existing is not None:
            n_docs = len(_store_doc_names(existing))
            print(f"[embedding] Store loaded ({n_docs} docs, up to date)",
                  file=sys.stderr, flush=True)
            return _store_passage_count(existing)
        n_ctx = len(_context_dir_doc_names(context_dir))
        n_store = len(_store_doc_names(existing)) if existing else 0
        print(
            f"[embedding] Store stale ({n_ctx} docs in context, "
            f"{n_store} in store), rebuilding",
            file=sys.stderr, flush=True,
        )

    st = _try_import_st()
    np = _try_import_numpy()
    if st is None or np is None:
        print("[embedding_store] sentence-transformers or numpy missing; "
              "skipping store build (Zipfian fallback active)", file=sys.stderr)
        return 0
    if not context_dir.exists():
        print(f"[embedding_store] context dir not found: {context_dir}", file=sys.stderr)
        return 0
    docs = sorted(p for p in context_dir.iterdir()
                  if p.is_file() and text_extract.is_corpus_file(p))
    if not docs:
        return 0

    print(f"[embedding_store] building from {len(docs)} documents in {context_dir}",
          file=sys.stderr, flush=True)

    # Per document: detect the dominant language, choose its embedding model, and
    # group passages by the model that will embed them. CORRECTNESS: passages
    # embedded by different models are NOT numerically comparable, so each model
    # gets its own sub-store and a query is only ever scored within one model's
    # sub-store (see query_store). The caller-supplied `model_name` is no longer
    # used to pick the model (per-document language drives selection now).
    groups: dict[str, list[dict]] = {}
    doc_models: dict[str, str] = {}
    passage_seq = 0
    for doc in docs:
        pages = text_extract.extract_pages(doc)
        if not pages:
            continue
        full_text = "\n".join(t for _, t in pages)
        lang = language_detect.detect_language(full_text)
        actual, _model = _resolve_model(st, model_for_language(lang))
        if actual is None:
            print("[embedding_store] no embedding model available; "
                  "Zipfian fallback active", file=sys.stderr)
            return 0
        doc_models[doc.name] = actual
        for page_no, page_text in pages:
            for chunk in _chunk_page(page_text):
                passage_seq += 1
                passage: dict[str, Any] = {
                    "doc_name": doc.name,
                    "doc_id": doc.stem,
                    "page": page_no,
                    "text": chunk,
                    "lang": lang,
                    "model_name": actual,
                }
                if reference_index is not None:
                    entry = reference_index.add(
                        input_type="context",
                        document_id=doc.stem,
                        document_name=doc.name,
                        location={"page": page_no, "paragraph": 0,
                                  "sentence": 0,
                                  "char_start": 0, "char_end": len(chunk)},
                        text_excerpt=reference_builder.excerpt(chunk),
                    )
                    passage["ref_id"] = entry.ref_id
                else:
                    passage["ref_id"] = f"REF-EMB-{passage_seq:05d}"
                groups.setdefault(actual, []).append(passage)

    if not groups:
        return 0

    # Encode each model's group with that model; store per-model sub-stores.
    models_block: dict[str, dict] = {}
    total = 0
    for mname, plist in groups.items():
        model = _load_model(st, mname)
        if model is None:
            print(f"[embedding_store] WARN: model {mname!r} unavailable at encode "
                  f"time; skipping {len(plist)} passages", file=sys.stderr)
            continue
        texts = [p["text"] for p in plist]
        t0 = time.monotonic()
        try:
            emb = model.encode(texts, batch_size=32, show_progress_bar=False,
                               convert_to_numpy=True, normalize_embeddings=True)
        except Exception as e:
            print(f"[embedding_store] encode failed for {mname!r} "
                  f"({type(e).__name__}: {e}); skipping", file=sys.stderr)
            continue
        models_block[mname] = {"passages": plist, "embeddings": emb.astype(np.float32)}
        total += len(plist)
        print(f"[embedding_store] embedded {len(plist)} passages with {mname!r} in "
              f"{time.monotonic() - t0:.1f}s", file=sys.stderr, flush=True)

    if not models_block:
        return 0

    store = {
        "schema": 2,
        "models": models_block,
        "doc_models": doc_models,
        "registry_signature": _registry_signature(),
    }
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("wb") as fh:
        pickle.dump(store, fh, protocol=pickle.HIGHEST_PROTOCOL)
    if reference_index is not None:
        reference_index.save()
    return total


def load_store(store_path: Path) -> dict | None:
    """Load the pickle. Returns None if the file doesn't exist or fails to load."""
    if not store_path.exists():
        return None
    try:
        with store_path.open("rb") as fh:
            return pickle.load(fh)
    except Exception as e:
        print(f"[embedding_store] load failed ({type(e).__name__}: {e})", file=sys.stderr)
        return None


def _context_dir_doc_names(context_dir: Path) -> set[str]:
    if not context_dir.exists():
        return set()
    return {p.name for p in context_dir.iterdir()
            if p.is_file() and text_extract.is_corpus_file(p)}


def _store_passages(store: dict):
    """Yield every passage across all model sub-stores (schema 2), or the flat
    passage list (legacy schema 1)."""
    models = store.get("models")
    if models is not None:
        for block in models.values():
            yield from (block.get("passages") or [])
    else:
        yield from (store.get("passages") or [])


def _store_passage_count(store: dict) -> int:
    return sum(1 for _ in _store_passages(store))


def passages(store: dict | None) -> list:
    """Public accessor for every passage across every schema-2 per-language
    sub-store, for callers outside this module (e.g. pipeline.py's boot log,
    which needs a real len(...) it can log without carrying passage TEXT itself
    per verify_session1.py check 112's len(...)-is-a-count-not-the-content-
    exemption). A schema-2 store has no top-level "passages" key, so
    store.get("passages", []) (what pipeline.py's boot log used before this)
    always read 0, even when the store held real passages (local D5)."""
    if not store:
        return []
    return list(_store_passages(store))


def _store_doc_names(store: dict) -> set[str]:
    return {p.get("doc_name") for p in _store_passages(store) if p.get("doc_name")}


def _configured_models() -> set:
    """The set of embedding model ids the engine is currently configured to use."""
    return {DEFAULT_MODEL_NAME, MULTILINGUAL_DEFAULT_MODEL, *LANG_MODEL_REGISTRY.values()}


def _store_model_names(store: dict) -> set:
    """The model ids actually used to build the store (schema-2 sub-store keys, with
    a fallback to per-passage model_name / legacy top-level model_name)."""
    names = set((store.get("models") or {}).keys())
    if not names:
        names = {p.get("model_name") for p in _store_passages(store) if p.get("model_name")}
    if not names and store.get("model_name"):
        names = {store.get("model_name")}
    return {n for n in names if n}


def is_store_stale(store: dict | None, context_dir: Path) -> tuple[bool, set[str], set[str]]:
    """Return (stale, added, removed). `stale` is True if any of: the store is
    missing; it predates the per-language schema (schema != 2); the stored embedding
    MODEL no longer matches the configured model (an explicit model-name check, so a
    model swap forces a rebuild even though the old pickle has different dimensions);
    the language->model registry changed (registry_signature mismatch); or the set of
    supported document filenames in context_dir differs from the doc_names recorded in
    the store."""
    if store is None:
        return (True, _context_dir_doc_names(context_dir), set())
    if store.get("schema") != 2:
        return (True, _context_dir_doc_names(context_dir), set())
    # Explicit model-name staleness: any model the store was built with that is not in
    # the current configured set means the store is from a different (or differently
    # dimensioned) model and MUST be rebuilt before query, never queried cross-model.
    stored_models = _store_model_names(store)
    if stored_models and not stored_models.issubset(_configured_models()):
        return (True, _context_dir_doc_names(context_dir), set())
    if store.get("registry_signature") != _registry_signature():
        return (True, _context_dir_doc_names(context_dir), set())
    current = _context_dir_doc_names(context_dir)
    stored = _store_doc_names(store)
    return (current != stored, current - stored, stored - current)


def query_store(store: dict, query_text: str, n: int = 20) -> list[dict]:
    """Return the top-n passages by cosine similarity across every model
    sub-store. Each result is the passage dict with `similarity` (float in
    [-1, 1]) added.

    CORRECTNESS: a query is embedded SEPARATELY by each sub-store's model and
    scored only against that sub-store's passages, so every similarity is a
    same-model cosine (the embedding math is always valid: passages and the
    query they are compared to were produced by the same model). Results from
    all sub-stores are then merged and the global top-n returned.

    Returns [] on any failure (missing library, empty store, bad query).
    """
    if not store or not query_text:
        return []
    st = _try_import_st()
    np = _try_import_numpy()
    if st is None or np is None:
        return []
    model_blocks = store.get("models")
    if model_blocks is None and store.get("passages") is not None:
        # Legacy schema-1 store: a single flat model.
        model_blocks = {
            (store.get("model_name") or DEFAULT_MODEL_NAME): {
                "passages": store.get("passages") or [],
                "embeddings": store.get("embeddings"),
            }
        }
    if not model_blocks:
        return []
    scored: list[dict] = []
    for mname, block in model_blocks.items():
        passages = block.get("passages") or []
        emb = block.get("embeddings")
        if not passages or emb is None or len(emb) == 0:
            continue
        model = _load_model(st, mname)
        if model is None:
            continue
        try:
            q = model.encode([query_text], convert_to_numpy=True,
                             normalize_embeddings=True)[0]
        except Exception as e:
            print(f"[embedding_store] query encode failed for {mname!r} "
                  f"({type(e).__name__}: {e})", file=sys.stderr)
            continue
        # Same-model: both query and passages were embedded by `mname`, both
        # L2-normalized, so dot product = cosine similarity.
        sims = emb @ q
        for i in range(len(passages)):
            rec = dict(passages[i])
            rec["similarity"] = float(sims[i])
            scored.append(rec)
    scored.sort(key=lambda r: r["similarity"], reverse=True)
    return scored[: max(0, n)]


def store_path_for(project_root: Path) -> Path:
    import durable_paths
    # Protected durable cache (INFRA-030): outside the auto-cleaned output tree.
    return durable_paths.embedding_store_path(project_root)


def get_or_build(project_root: Path, *, reference_index: Any = None) -> dict | None:
    """Boot-time convenience wrapper around build_store. The staleness
    decision (load existing pickle vs. rebuild) lives inside build_store
    itself, so this function simply triggers the build/load and returns
    the resulting store dict (or None on graceful degradation)."""
    path = store_path_for(project_root)
    context_dir = project_root / "input" / "context"
    n = build_store(context_dir, path, reference_index=reference_index)
    if n == 0:
        return None
    return load_store(path)

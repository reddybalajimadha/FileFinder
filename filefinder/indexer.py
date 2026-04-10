"""Embedding computation and disk-based caching.

Computes sentence-transformer embeddings for documents and caches them
to avoid reprocessing on subsequent runs. The cache is invalidated
per-file when the file's modification time changes.
"""

import hashlib
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

CACHE_DIR = ".filefinder_cache"
CACHE_FILE = "embeddings.json"


def get_cache_path(directory):
    """Return the cache file path for a given scan directory."""
    cache_dir = os.path.join(directory, CACHE_DIR)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, CACHE_FILE)


def _file_fingerprint(file_path):
    """Generate a fingerprint based on path, size, and modification time."""
    stat = os.stat(file_path)
    raw = f"{file_path}|{stat.st_size}|{stat.st_mtime}"
    return hashlib.md5(raw.encode()).hexdigest()


def load_cache(directory):
    """Load cached embeddings metadata from disk."""
    cache_path = get_cache_path(directory)
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Cache corrupted, rebuilding: %s", e)
        return {}


def save_cache(directory, cache_data):
    """Save embeddings metadata to disk cache."""
    cache_path = get_cache_path(directory)
    with open(cache_path, "w") as f:
        json.dump(cache_data, f, indent=2)
    logger.debug("Cache saved to %s", cache_path)


def build_index(model, files, extract_fn, directory, force_reindex=False):
    """Build embeddings index with caching support.

    Args:
        model: SentenceTransformer model instance.
        files: List of file paths to index.
        extract_fn: Callable that takes a file path and returns text or None.
        directory: Base directory (used for cache location).
        force_reindex: If True, ignore cache and recompute all embeddings.

    Returns:
        dict mapping file_path -> embedding tensor.
    """
    import torch

    cache = {} if force_reindex else load_cache(directory)
    embeddings = {}
    texts_to_encode = []
    files_to_encode = []
    cached_count = 0
    skipped_count = 0

    for file_path in files:
        fingerprint = _file_fingerprint(file_path)

        # Check cache: if fingerprint matches, reuse stored embedding
        if file_path in cache and cache[file_path].get("fingerprint") == fingerprint:
            stored = cache[file_path]["embedding"]
            embeddings[file_path] = torch.tensor(stored)
            cached_count += 1
            continue

        # Extract text for new/changed files
        text = extract_fn(file_path)
        if not text or len(text.strip()) < 10:
            logger.debug("Skipping %s (no meaningful text extracted)", file_path)
            skipped_count += 1
            continue

        texts_to_encode.append(text)
        files_to_encode.append(file_path)

    # Batch encode all new texts at once (much faster than one-by-one)
    if texts_to_encode:
        logger.info("Encoding %d new documents...", len(texts_to_encode))
        new_embeddings = model.encode(
            texts_to_encode, convert_to_tensor=True, show_progress_bar=True
        )

        # Handle single vs multiple results
        if len(texts_to_encode) == 1:
            new_embeddings = new_embeddings.unsqueeze(0)

        new_cache = load_cache(directory) if not force_reindex else {}
        for i, file_path in enumerate(files_to_encode):
            emb = new_embeddings[i]
            embeddings[file_path] = emb
            new_cache[file_path] = {
                "fingerprint": _file_fingerprint(file_path),
                "embedding": emb.tolist(),
            }

        # Merge with existing cache
        cache.update(new_cache)
        save_cache(directory, cache)

    logger.info(
        "Index built: %d cached, %d new, %d skipped",
        cached_count,
        len(texts_to_encode),
        skipped_count,
    )
    return embeddings

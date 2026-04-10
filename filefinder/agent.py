"""FileFinder Agent - the brain that orchestrates indexing and search.

Handles:
- Tier 1: Fast filename/metadata scan → SQLite
- Tier 2: Background content extraction → SQLite FTS5
- Tier 3: Semantic search via embeddings (lazy-loaded, only when needed)
- File operations: open, reveal in file manager
"""

import logging
import os
import platform
import subprocess
import threading
import time

from .extractor import can_extract, extract_text
from .scanner import scan_directory
from .store import FileStore

logger = logging.getLogger(__name__)


class FileFinderAgent:
    """Main agent that manages indexing and search."""

    def __init__(self, directory, pdf_page_limit=5):
        self.directory = os.path.abspath(directory)
        self.store = FileStore(self.directory)
        self.pdf_page_limit = pdf_page_limit
        self._semantic_model = None
        self._embeddings = {}
        self._bg_thread = None
        self._bg_stop = threading.Event()

    def initialize(self):
        """Run Tier 1 scan: fast metadata indexing.

        This scans all filenames, sizes, dates, extensions into SQLite.
        Takes seconds even for large directories.
        """
        self.store.open()

        logger.info("Tier 1: Scanning filesystem metadata...")
        start = time.time()

        batch = []
        batch_size = 500
        total = 0

        for meta in scan_directory(self.directory):
            batch.append(meta)
            total += 1
            if len(batch) >= batch_size:
                self.store.upsert_batch(batch)
                batch = []

        if batch:
            self.store.upsert_batch(batch)

        # Clean up entries for deleted files
        removed = self.store.remove_missing_files()

        elapsed = time.time() - start
        logger.info(
            "Tier 1 complete: %d files indexed in %.1fs (%d stale removed)",
            total, elapsed, removed,
        )
        return total

    def index_content(self, background=True):
        """Run Tier 2: extract text content from files.

        Args:
            background: If True, runs in a background thread so the user
                       can start searching immediately.
        """
        if background:
            self._bg_stop.clear()
            self._bg_thread = threading.Thread(
                target=self._content_indexing_worker,
                daemon=True,
            )
            self._bg_thread.start()
            logger.info("Tier 2: Content extraction started in background.")
        else:
            self._content_indexing_worker()

    def _content_indexing_worker(self):
        """Background worker that extracts content from pending files."""
        # Prioritize common document types first
        priority_exts = [".pdf", ".docx", ".txt", ".md", ".html", ".htm"]
        other_exts = [
            ext for ext in [
                ".csv", ".json", ".xml", ".yaml", ".yml",
                ".py", ".js", ".ts", ".java", ".c", ".cpp",
                ".go", ".rs", ".rb", ".sql", ".sh", ".log",
                ".ini", ".cfg", ".conf", ".toml", ".rst",
                ".h", ".php", ".bat", ".ps1", ".r", ".m",
                ".swift", ".kt", ".scala",
            ]
        ]

        all_exts = priority_exts + other_exts
        pending = self.store.get_pending_content_files(all_exts)

        if not pending:
            logger.info("Tier 2: No pending files to extract content from.")
            return

        logger.info("Tier 2: Extracting content from %d files...", len(pending))
        indexed = 0
        failed = 0

        for row in pending:
            if self._bg_stop.is_set():
                logger.info("Tier 2: Content extraction stopped early.")
                break

            path = row["path"]
            ext = row["extension"]

            if not can_extract(ext):
                self.store.update_content(path, None, status="skipped")
                continue

            text = extract_text(
                path, use_ocr=False, pdf_page_limit=self.pdf_page_limit
            )

            if text and len(text.strip()) > 10:
                self.store.update_content(path, text, status="indexed")
                indexed += 1
            else:
                self.store.update_content(path, None, status="failed")
                failed += 1

        logger.info(
            "Tier 2 complete: %d extracted, %d failed", indexed, failed
        )

    def search(self, query, limit=10):
        """Smart search: picks the best strategy for the query.

        1. Always does keyword search (FTS5) - instant
        2. Also does filename search - catches partial matches
        3. Merges and deduplicates results

        Args:
            query: Natural language search query.
            limit: Max results to return.

        Returns:
            List of result dicts with path, name, relevance info, match_type.
        """
        results = {}

        # Keyword search (FTS5 - searches filenames + content)
        fts_results = self.store.search_keyword(query, limit=limit)
        for r in fts_results:
            r["match_type"] = "content+name"
            results[r["path"]] = r

        # Filename LIKE search (catches partial matches FTS5 might miss)
        name_results = self.store.search_filename(query, limit=limit)
        for r in name_results:
            if r["path"] not in results:
                r["match_type"] = "filename"
                r["relevance"] = -0.5  # Lower priority than FTS
                results[r["path"]] = r

        # Sort: FTS results first (better relevance), then filename matches
        sorted_results = sorted(
            results.values(),
            key=lambda x: x.get("relevance", 0),
        )
        return sorted_results[:limit]

    def search_semantic(self, query, top_k=5):
        """Tier 3: Semantic search using transformer embeddings.

        Only loads the model when this method is actually called.
        Falls back gracefully if sentence-transformers isn't installed.

        Args:
            query: Natural language query.
            top_k: Number of results.

        Returns:
            List of (path, score) tuples.
        """
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install it for semantic search: pip install sentence-transformers"
            )
            return []

        # Lazy load model
        if self._semantic_model is None:
            logger.info("Loading semantic search model...")
            self._semantic_model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            )

        # Build embeddings from indexed content
        if not self._embeddings:
            self._build_embeddings()

        if not self._embeddings:
            logger.info("No document embeddings available for semantic search.")
            return []

        query_emb = self._semantic_model.encode(query, convert_to_tensor=True)

        results = []
        for path, emb in self._embeddings.items():
            score = util.pytorch_cos_sim(query_emb, emb).item()
            results.append((path, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _build_embeddings(self):
        """Build embeddings from files that have content indexed."""
        rows = self.store.conn.execute(
            "SELECT path, content FROM files WHERE content_status = 'indexed' AND content IS NOT NULL"
        ).fetchall()

        if not rows:
            return

        paths = [r["path"] for r in rows]
        texts = [r["content"] for r in rows]

        logger.info("Building embeddings for %d documents...", len(texts))
        embs = self._semantic_model.encode(
            texts, convert_to_tensor=True, show_progress_bar=True
        )

        if len(texts) == 1:
            embs = embs.unsqueeze(0)

        for i, path in enumerate(paths):
            self._embeddings[path] = embs[i]

    def search_by_type(self, extension, limit=20):
        """Find files by extension."""
        return self.store.search_by_extension(extension, limit=limit)

    def get_stats(self):
        """Get index statistics."""
        return self.store.get_stats()

    def open_file(self, file_path):
        """Open a file with the system's default application."""
        if not os.path.exists(file_path):
            logger.error("File not found: %s", file_path)
            return False

        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            else:
                subprocess.Popen(["xdg-open", file_path])
            return True
        except Exception as e:
            logger.error("Failed to open %s: %s", file_path, e)
            return False

    def reveal_file(self, file_path):
        """Reveal a file in the system file manager."""
        if not os.path.exists(file_path):
            logger.error("File not found: %s", file_path)
            return False

        parent = os.path.dirname(file_path)
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["open", "-R", file_path])
            elif system == "Windows":
                subprocess.Popen(["explorer", "/select,", file_path])
            else:
                subprocess.Popen(["xdg-open", parent])
            return True
        except Exception as e:
            logger.error("Failed to reveal %s: %s", file_path, e)
            return False

    def stop(self):
        """Stop background tasks and close the store."""
        self._bg_stop.set()
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=2)
        self.store.close()

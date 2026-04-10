"""Semantic search engine using transformer embeddings."""

import logging
import os

from sentence_transformers import SentenceTransformer, util

from .extractor import extract_text, scan_files
from .indexer import build_index

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class FileSearcher:
    """Semantic file search engine.

    Indexes files in a directory using sentence-transformer embeddings
    and supports natural language queries to find the most relevant files.
    """

    def __init__(self, directory, model_name=DEFAULT_MODEL, pdf_page_limit=5):
        self.directory = os.path.abspath(directory)
        self.model_name = model_name
        self.pdf_page_limit = pdf_page_limit
        self.model = None
        self.embeddings = {}

    def load_model(self):
        """Load the sentence-transformer model."""
        logger.info("Loading model: %s", self.model_name)
        self.model = SentenceTransformer(self.model_name)
        logger.info("Model loaded successfully.")

    def index(self, force_reindex=False):
        """Scan and index all supported files in the directory."""
        if self.model is None:
            self.load_model()

        files = scan_files(self.directory)
        if not files:
            logger.warning("No supported files found in %s", self.directory)
            return 0

        logger.info("Indexing %d files...", len(files))

        def _extract(path):
            return extract_text(path, pdf_page_limit=self.pdf_page_limit)

        self.embeddings = build_index(
            self.model, files, _extract, self.directory,
            force_reindex=force_reindex,
        )
        return len(self.embeddings)

    def search(self, query, top_k=5, threshold=0.0):
        """Search indexed files using a natural language query.

        Args:
            query: Natural language search query.
            top_k: Number of top results to return.
            threshold: Minimum similarity score (0.0 to 1.0).

        Returns:
            List of (file_path, score) tuples, sorted by relevance.
        """
        if not self.embeddings:
            logger.error("No files indexed. Run .index() first.")
            return []

        if self.model is None:
            self.load_model()

        query_embedding = self.model.encode(query, convert_to_tensor=True)

        results = []
        for file_path, embedding in self.embeddings.items():
            score = util.pytorch_cos_sim(query_embedding, embedding).item()
            if score >= threshold:
                results.append((file_path, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

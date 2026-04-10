"""SQLite + FTS5 storage layer.

Stores file metadata and extracted content in SQLite with full-text search
indexes for fast keyword-based retrieval. This is the backbone of Tier 1
(filename/metadata) and Tier 2 (content) search.
"""

import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DB_FILENAME = "filefinder.db"


class FileStore:
    """SQLite-backed file index with FTS5 full-text search."""

    def __init__(self, db_dir):
        """Initialize the store.

        Args:
            db_dir: Directory to store the database file.
                   Creates a .filefinder/ subdirectory.
        """
        self.store_dir = os.path.join(os.path.abspath(db_dir), ".filefinder")
        os.makedirs(self.store_dir, exist_ok=True)
        self.db_path = os.path.join(self.store_dir, DB_FILENAME)
        self.conn = None

    def open(self):
        """Open the database connection and ensure schema exists."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        self._create_schema()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def _create_schema(self):
        """Create tables and FTS5 indexes if they don't exist."""
        self.conn.executescript("""
            -- Main file metadata table
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                extension TEXT,
                size_bytes INTEGER,
                modified_time TEXT,
                created_time TEXT,
                parent_dir TEXT,
                content TEXT,
                content_status TEXT DEFAULT 'pending',
                fingerprint TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- FTS5 index on filename + path + content for fast text search
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                name, path, parent_dir, content, extension,
                content='files',
                content_rowid='id',
                tokenize='porter unicode61'
            );

            -- Triggers to keep FTS in sync with main table
            CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                INSERT INTO files_fts(rowid, name, path, parent_dir, content, extension)
                VALUES (new.id, new.name, new.path, new.parent_dir, new.content, new.extension);
            END;

            CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                INSERT INTO files_fts(files_fts, rowid, name, path, parent_dir, content, extension)
                VALUES ('delete', old.id, old.name, old.path, old.parent_dir, old.content, old.extension);
            END;

            CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
                INSERT INTO files_fts(files_fts, rowid, name, path, parent_dir, content, extension)
                VALUES ('delete', old.id, old.name, old.path, old.parent_dir, old.content, old.extension);
                INSERT INTO files_fts(rowid, name, path, parent_dir, content, extension)
                VALUES (new.id, new.name, new.path, new.parent_dir, new.content, new.extension);
            END;

            -- Schema version tracking
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            -- Index for fast path lookups
            CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
            CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
            CREATE INDEX IF NOT EXISTS idx_files_content_status ON files(content_status);
        """)
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self.conn.commit()

    def upsert_file(self, metadata):
        """Insert or update a file's metadata.

        Args:
            metadata: dict with keys from scanner (path, name, extension, etc.)
        """
        self.conn.execute("""
            INSERT INTO files (path, name, extension, size_bytes,
                              modified_time, created_time, parent_dir, fingerprint)
            VALUES (:path, :name, :extension, :size_bytes,
                    :modified_time, :created_time, :parent_dir, :fingerprint)
            ON CONFLICT(path) DO UPDATE SET
                name=excluded.name,
                extension=excluded.extension,
                size_bytes=excluded.size_bytes,
                modified_time=excluded.modified_time,
                created_time=excluded.created_time,
                parent_dir=excluded.parent_dir,
                fingerprint=excluded.fingerprint,
                indexed_at=CURRENT_TIMESTAMP
        """, {
            **metadata,
            "fingerprint": f"{metadata['size_bytes']}|{metadata['modified_time']}",
        })

    def upsert_batch(self, metadata_list):
        """Insert or update multiple files efficiently."""
        for meta in metadata_list:
            self.upsert_file(meta)
        self.conn.commit()
        logger.debug("Batch upserted %d files", len(metadata_list))

    def update_content(self, path, content, status="indexed"):
        """Update the extracted text content for a file.

        Args:
            path: File path.
            content: Extracted text content.
            status: Content status ('indexed', 'failed', 'skipped').
        """
        self.conn.execute(
            "UPDATE files SET content = ?, content_status = ? WHERE path = ?",
            (content, status, path),
        )
        self.conn.commit()

    def get_pending_content_files(self, extensions=None):
        """Get files that haven't had content extracted yet.

        Args:
            extensions: Optional list of extensions to filter (e.g. ['.pdf', '.txt']).

        Returns:
            List of Row objects with path, extension, size_bytes.
        """
        if extensions:
            placeholders = ",".join("?" * len(extensions))
            return self.conn.execute(
                f"SELECT path, extension, size_bytes FROM files "
                f"WHERE content_status = 'pending' AND extension IN ({placeholders}) "
                f"ORDER BY size_bytes ASC",
                extensions,
            ).fetchall()
        return self.conn.execute(
            "SELECT path, extension, size_bytes FROM files "
            "WHERE content_status = 'pending' ORDER BY size_bytes ASC"
        ).fetchall()

    def search_keyword(self, query, limit=20):
        """Search using FTS5 keyword matching.

        This is the fast Tier 1+2 search. Matches against filenames,
        paths, and content.

        Args:
            query: Search query string.
            limit: Max number of results.

        Returns:
            List of dicts with file info and relevance rank.
        """
        # FTS5 uses a special MATCH syntax. We escape user input for safety.
        safe_query = _fts5_safe_query(query)
        if not safe_query:
            return []

        try:
            rows = self.conn.execute("""
                SELECT f.path, f.name, f.extension, f.size_bytes,
                       f.modified_time, f.parent_dir, f.content_status,
                       rank AS relevance
                FROM files_fts fts
                JOIN files f ON f.id = fts.rowid
                WHERE files_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit)).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError as e:
            logger.debug("FTS query failed for '%s': %s", query, e)
            return []

    def search_filename(self, query, limit=20):
        """Search only by filename (fast, always available)."""
        pattern = f"%{query}%"
        rows = self.conn.execute("""
            SELECT path, name, extension, size_bytes, modified_time,
                   parent_dir, content_status
            FROM files
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY modified_time DESC
            LIMIT ?
        """, (pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    def search_by_extension(self, extension, limit=50):
        """Find all files with a given extension."""
        if not extension.startswith("."):
            extension = f".{extension}"
        rows = self.conn.execute("""
            SELECT path, name, size_bytes, modified_time, parent_dir
            FROM files
            WHERE extension = ?
            ORDER BY modified_time DESC
            LIMIT ?
        """, (extension.lower(), limit)).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self):
        """Get index statistics."""
        row = self.conn.execute("""
            SELECT
                COUNT(*) as total_files,
                SUM(CASE WHEN content_status = 'indexed' THEN 1 ELSE 0 END) as content_indexed,
                SUM(CASE WHEN content_status = 'pending' THEN 1 ELSE 0 END) as content_pending,
                SUM(size_bytes) as total_size_bytes,
                COUNT(DISTINCT extension) as unique_extensions
            FROM files
        """).fetchone()
        return dict(row)

    def get_file(self, path):
        """Get a single file's full record."""
        row = self.conn.execute(
            "SELECT * FROM files WHERE path = ?", (path,)
        ).fetchone()
        return dict(row) if row else None

    def remove_missing_files(self):
        """Remove entries for files that no longer exist on disk."""
        rows = self.conn.execute("SELECT id, path FROM files").fetchall()
        removed = 0
        for row in rows:
            if not os.path.exists(row["path"]):
                self.conn.execute("DELETE FROM files WHERE id = ?", (row["id"],))
                removed += 1
        if removed:
            self.conn.commit()
            logger.info("Removed %d stale entries for deleted files", removed)
        return removed

    def file_count(self):
        """Return total number of indexed files."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM files").fetchone()
        return row["cnt"]


def _fts5_safe_query(query):
    """Convert a natural language query to FTS5 safe query.

    Splits into tokens and joins with OR for broad matching.
    Strips special FTS5 characters to prevent injection.
    """
    # Remove FTS5 special chars
    unsafe = set('"*^:{}[]()+-<>~@#$%&|\\/')
    cleaned = "".join(c if c not in unsafe else " " for c in query)
    tokens = cleaned.split()
    tokens = [t for t in tokens if len(t) > 1]  # Drop single chars
    if not tokens:
        return None
    # Use OR matching so any token hit counts
    return " OR ".join(tokens)

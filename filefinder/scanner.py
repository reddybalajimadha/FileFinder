"""Filesystem scanner with security-aware exclusions.

Walks directories collecting file metadata (name, path, size, dates, extension)
while skipping sensitive directories and files by default.
"""

import os
import stat
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Directories that should NEVER be indexed (security + noise)
DEFAULT_EXCLUDED_DIRS = {
    # Security-sensitive
    ".ssh", ".gnupg", ".gpg", ".pki", ".cert", ".certs",
    ".password-store", ".credentials", ".secrets",
    # Browser/app data (contains credentials, cookies)
    ".mozilla", ".chrome", ".config/google-chrome",
    ".config/chromium", ".config/BraveSoftware",
    # Environment / tokens
    ".aws", ".azure", ".gcloud", ".kube", ".docker",
    ".npm", ".pypirc",
    # Version control internals
    ".git", ".svn", ".hg",
    # OS junk
    ".Trash", "$RECYCLE.BIN", "System Volume Information",
    # Package/build dirs (huge, not useful to search)
    "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".eggs", "dist", "build", ".cache",
    # Our own cache
    ".filefinder",
}

# File patterns to never index (contain secrets or are binary noise)
DEFAULT_EXCLUDED_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    ".netrc", ".npmrc", ".pypirc",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    "credentials.json", "service-account.json", "token.json",
    "*.key", "*.pem", "*.p12", "*.pfx", "*.keystore",
}

# Max file size to even consider (skip huge binaries)
MAX_FILE_SIZE_MB = 100


def _is_excluded_dir(dirname):
    """Check if a directory name should be skipped."""
    return dirname in DEFAULT_EXCLUDED_DIRS or dirname.startswith(".")


def _is_excluded_file(filename):
    """Check if a file should be skipped based on name patterns."""
    if filename in DEFAULT_EXCLUDED_FILES:
        return True
    for pattern in DEFAULT_EXCLUDED_FILES:
        if pattern.startswith("*") and filename.endswith(pattern[1:]):
            return True
    return False


def _get_file_metadata(file_path):
    """Extract metadata from a file without reading its contents."""
    try:
        st = os.stat(file_path)
        return {
            "path": file_path,
            "name": os.path.basename(file_path),
            "extension": os.path.splitext(file_path)[1].lower(),
            "size_bytes": st.st_size,
            "modified_time": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "created_time": datetime.fromtimestamp(st.st_ctime).isoformat(),
            "parent_dir": os.path.dirname(file_path),
        }
    except (OSError, PermissionError) as e:
        logger.debug("Cannot stat %s: %s", file_path, e)
        return None


def scan_directory(directory, include_hidden=False):
    """Scan a directory and yield file metadata dicts.

    This is Tier 1 - fast metadata-only scan. No file contents are read.

    Args:
        directory: Root directory to scan.
        include_hidden: If True, include hidden files (still excludes
                       security-sensitive dirs).

    Yields:
        dict with keys: path, name, extension, size_bytes,
        modified_time, created_time, parent_dir
    """
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    file_count = 0
    skipped_count = 0

    for root, dirs, files in os.walk(directory):
        # Filter out excluded directories IN-PLACE (prevents os.walk from descending)
        dirs[:] = [
            d for d in dirs
            if d not in DEFAULT_EXCLUDED_DIRS
            and (include_hidden or not d.startswith("."))
        ]

        for fname in files:
            # Skip excluded files
            if _is_excluded_file(fname):
                skipped_count += 1
                continue

            # Skip hidden files unless requested
            if not include_hidden and fname.startswith("."):
                skipped_count += 1
                continue

            file_path = os.path.join(root, fname)

            # Skip files that are too large
            try:
                size = os.path.getsize(file_path)
                if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    skipped_count += 1
                    continue
                if size == 0:
                    skipped_count += 1
                    continue
            except (OSError, PermissionError):
                skipped_count += 1
                continue

            meta = _get_file_metadata(file_path)
            if meta:
                file_count += 1
                yield meta

    logger.info(
        "Scan complete: %d files found, %d skipped (excluded/hidden/too large)",
        file_count, skipped_count,
    )

"""FastAPI backend for the FileFinder desktop app.

Exposes HTTP endpoints that the HTML/JS frontend calls. The server is
bound to 127.0.0.1 only (never exposed on the network) for security.
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..agent import FileFinderAgent

logger = logging.getLogger(__name__)

# Global agent instance - initialized when a directory is selected
_agent: Optional[FileFinderAgent] = None
_agent_lock = threading.Lock()
_current_directory: Optional[str] = None

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="FileFinder", version="0.4.0")


# --- Request/Response models ---

class IndexRequest(BaseModel):
    directory: str


class OpenRequest(BaseModel):
    path: str


class SearchResult(BaseModel):
    path: str
    name: str
    extension: Optional[str] = None
    size_bytes: Optional[int] = None
    modified_time: Optional[str] = None
    parent_dir: Optional[str] = None
    match_type: Optional[str] = None
    content_status: Optional[str] = None
    relevance: Optional[float] = None


# --- Endpoints ---

@app.get("/api/health")
async def health():
    """Health check - always available."""
    return {"status": "ok", "indexed_directory": _current_directory}


@app.post("/api/index")
async def index_directory(req: IndexRequest):
    """Index a directory (Tier 1 + start Tier 2 in background)."""
    global _agent, _current_directory

    directory = os.path.abspath(os.path.expanduser(req.directory))
    if not os.path.isdir(directory):
        raise HTTPException(404, f"Directory not found: {directory}")

    with _agent_lock:
        # Stop existing agent if any
        if _agent is not None:
            _agent.stop()

        _agent = FileFinderAgent(directory)
        try:
            count = _agent.initialize()
        except Exception as e:
            logger.exception("Failed to initialize agent")
            raise HTTPException(500, f"Indexing failed: {e}")

        _agent.index_content(background=True)
        _current_directory = directory

    return {
        "directory": directory,
        "file_count": count,
        "status": "indexed",
        "message": "Content extraction running in background",
    }


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    semantic: bool = Query(False, description="Use AI semantic search"),
):
    """Search indexed files."""
    if _agent is None:
        raise HTTPException(400, "No directory indexed. Call /api/index first.")

    with _agent_lock:
        if semantic:
            raw = _agent.search_semantic(q, top_k=limit)
            results = []
            for path, score in raw:
                meta = _agent.store.get_file(path)
                if meta:
                    meta["relevance"] = score
                    meta["match_type"] = "semantic"
                    results.append(meta)
        else:
            results = _agent.search(q, limit=limit)

    return {"query": q, "count": len(results), "results": results}


@app.get("/api/stats")
async def stats():
    """Get index statistics."""
    if _agent is None:
        return {"indexed": False}

    with _agent_lock:
        stats_data = _agent.get_stats()

    return {
        "indexed": True,
        "directory": _current_directory,
        **stats_data,
    }


@app.get("/api/by-type")
async def search_by_type(
    extension: str = Query(..., description="File extension (e.g. pdf)"),
    limit: int = Query(50, ge=1, le=200),
):
    """List files by extension."""
    if _agent is None:
        raise HTTPException(400, "No directory indexed.")

    with _agent_lock:
        results = _agent.search_by_type(extension, limit=limit)

    return {"extension": extension, "count": len(results), "results": results}


@app.post("/api/open")
async def open_file(req: OpenRequest):
    """Open a file with the system default application."""
    if _agent is None:
        raise HTTPException(400, "Agent not initialized.")

    if not os.path.exists(req.path):
        raise HTTPException(404, "File does not exist.")

    success = _agent.open_file(req.path)
    if not success:
        raise HTTPException(500, "Failed to open file.")
    return {"status": "opened", "path": req.path}


@app.post("/api/reveal")
async def reveal_file(req: OpenRequest):
    """Reveal a file in the system file manager (Explorer on Windows)."""
    if _agent is None:
        raise HTTPException(400, "Agent not initialized.")

    if not os.path.exists(req.path):
        raise HTTPException(404, "File does not exist.")

    success = _agent.reveal_file(req.path)
    if not success:
        raise HTTPException(500, "Failed to reveal file.")
    return {"status": "revealed", "path": req.path}


@app.get("/api/browse")
async def browse(path: str = Query(..., description="Directory path")):
    """List contents of a directory (for folder tree navigation)."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        raise HTTPException(404, "Directory not found.")

    try:
        entries = []
        for name in sorted(os.listdir(path)):
            if name.startswith("."):
                continue
            full = os.path.join(path, name)
            try:
                is_dir = os.path.isdir(full)
                entries.append({
                    "name": name,
                    "path": full,
                    "is_dir": is_dir,
                    "size": os.path.getsize(full) if not is_dir else None,
                })
            except (OSError, PermissionError):
                continue
    except PermissionError:
        raise HTTPException(403, "Permission denied.")

    return {"path": path, "entries": entries}


# --- Static file serving (the frontend) ---

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    """Serve the frontend HTML."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(
            {"error": "Frontend not built. Static files missing."},
            status_code=500,
        )
    return FileResponse(str(index_file))


def shutdown():
    """Clean up the agent on server shutdown."""
    global _agent
    if _agent is not None:
        _agent.stop()
        _agent = None


@app.on_event("shutdown")
async def on_shutdown():
    shutdown()

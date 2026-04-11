# FileFinder

An AI-powered file search desktop application. Find files using natural language queries through a modern Windows/macOS/Linux app, or via CLI.

## Features

- **Native Desktop App** - Runs as a real Windows application (via PyWebView)
- **Modern UI** - Clean interface with live search, dark mode, file previews
- **Tiered Search** - Instant filename search + background content indexing + optional AI semantic search
- **Built-in File Operations** - Click to open files, right-click to reveal in file manager
- **Security-First** - Auto-excludes sensitive dirs (.ssh, .env, credentials, etc.)
- **100% Local** - No data sent to external servers. Everything runs on your machine.
- **Multi-Format** - Searches PDF, DOCX, TXT, MD, code files (Python, JS, Java, C++, etc.), config files, and more

## How It Works

FileFinder uses a **tiered search architecture** so you get results fast:

| Tier | What | Speed | How |
|------|------|-------|-----|
| **Tier 1** | Filenames, paths, sizes, dates | **Instant** (seconds to index) | SQLite + FTS5 |
| **Tier 2** | Document content (PDF text, code, docs) | **Background** (auto-extracts) | SQLite FTS5 |
| **Tier 3** | Semantic/meaning search | **On-demand** | Transformer embeddings |

You can start searching **immediately** after Tier 1 completes. Content extraction runs in the background while you work.

## Installation

### Option 1: Desktop App (Recommended)

```bash
git clone https://github.com/reddybalajimadha/FileFinder.git
cd FileFinder
pip install -r requirements.txt

# Launch the desktop app
python -m filefinder.web
```

A native window will open with the FileFinder UI.

### Option 2: CLI only

```bash
# Minimum (keyword search only - no extra dependencies!)
python -m filefinder ~/Documents
```

### Building a Windows .exe

See [BUILD_WINDOWS.md](BUILD_WINDOWS.md) for step-by-step instructions on packaging FileFinder as a standalone Windows application with PyInstaller.

Quick version:
```powershell
pip install -r requirements.txt
pyinstaller filefinder.spec
# Output: dist\FileFinder\FileFinder.exe
```

## Usage

### Desktop App
```bash
python -m filefinder.web                    # Open app, pick folder from UI
python -m filefinder.web ~/Documents        # Auto-index on startup
```

Once the app opens:
1. Click **Select Folder** to choose a directory to index
2. Type your search query - results appear live as you type
3. Click any result to open the file
4. Click **Reveal** to show a file in your file manager
5. Use the **AI Search** toggle for semantic search (needs sentence-transformers)

### CLI (Interactive Mode)
```bash
python -m filefinder ~/Documents
```

```
FileFinder> find my resume
  [1] Resume_2024.pdf                        245KB [content matched]
      /home/user/Documents/Resume_2024.pdf
  [2] resume_draft.docx                       52KB [name matched]
      /home/user/Documents/drafts/resume_draft.docx

  2 results. Use 'open <number>' or 'reveal <number>'.

FileFinder> open 1
Opening: /home/user/Documents/Resume_2024.pdf
```

### CLI Options
```
--semantic       Use transformer-based AI search (slower, smarter)
--type EXT       Find files by extension (e.g. --type pdf)
--limit N        Max results (default: 10)
--stats          Show index statistics
--reindex        Force full reindex
--no-content     Skip content extraction (fast metadata-only mode)
--verbose        Debug logging
```

## Security

FileFinder automatically skips sensitive directories and files:
- `.ssh`, `.gnupg`, `.aws`, `.kube`, `.docker` (credentials)
- `.env` files, private keys, tokens (secrets)
- Browser profiles (cookies, passwords)
- `node_modules`, `__pycache__`, `.venv` (noise)

The web server always binds to `127.0.0.1` only - never exposed on the network.

## Project Structure

```
FileFinder/
├── filefinder/
│   ├── __init__.py
│   ├── __main__.py         # CLI entry point
│   ├── agent.py            # Orchestrates indexing + search
│   ├── cli.py              # Interactive command-line interface
│   ├── extractor.py        # Text extraction (PDF, DOCX, TXT, code...)
│   ├── scanner.py          # Filesystem walker with security exclusions
│   ├── store.py            # SQLite + FTS5 storage
│   └── web/
│       ├── __init__.py
│       ├── __main__.py     # Desktop app entry point
│       ├── desktop.py      # PyWebView native window launcher
│       ├── server.py       # FastAPI backend
│       └── static/
│           ├── index.html  # UI markup
│           ├── style.css   # UI styles
│           └── app.js      # UI logic
├── filefinder.spec         # PyInstaller build spec
├── BUILD_WINDOWS.md        # Windows .exe build guide
├── requirements.txt
└── README.md
```

## Supported File Types

**Content extraction (Tier 2):**
- Documents: PDF, DOCX, TXT, MD, RST, CSV
- Code: Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, Ruby, PHP, SQL, Shell
- Config: JSON, XML, YAML, TOML, INI, HTML

All other files are still searchable by filename/metadata (Tier 1).

## Roadmap

- [x] Tiered SQLite + transformer architecture
- [x] Desktop GUI with PyWebView
- [x] Windows .exe packaging
- [ ] File system watcher for live index updates
- [ ] Thumbnail previews for images/PDFs
- [ ] File operations: rename, delete, move
- [ ] Drag & drop support
- [ ] System tray integration with background daemon
- [ ] Voice command support
- [ ] Image OCR (find text in screenshots)
- [ ] macOS `.app` and Linux `.AppImage` builds

## Contributing

Contributions are welcome! Fork this repository, make your changes, and submit a pull request.

## License

See repository for license details.

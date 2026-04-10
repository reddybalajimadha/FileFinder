# FileFinder

An AI-powered file search agent that lets you find files using natural language. Works like a smart file manager - indexes your files once, then answers queries instantly.

## How It Works

FileFinder uses a **tiered search architecture** so you get results fast:

| Tier | What | Speed | How |
|------|------|-------|-----|
| **Tier 1** | Filenames, paths, sizes, dates | **Instant** (seconds to index) | SQLite + FTS5 |
| **Tier 2** | Document content (PDF text, code, docs) | **Background** (auto-extracts) | SQLite FTS5 |
| **Tier 3** | Semantic/meaning search | **On-demand** (needs `--semantic`) | Transformer embeddings |

You can start searching **immediately** after the Tier 1 scan completes. Content extraction runs in the background.

## Security

FileFinder automatically skips sensitive directories and files:
- `.ssh`, `.gnupg`, `.aws`, `.kube`, `.docker` (credentials)
- `.env` files, private keys, tokens (secrets)
- Browser profiles (cookies, passwords)
- Everything stays **100% local** - no data is sent anywhere

## Installation

**Minimum (keyword search only - no extra dependencies!):**
```bash
# SQLite FTS5 is built into Python 3.8+, so basic search just works
git clone https://github.com/reddybalajimadha/FileFinder.git
cd FileFinder
```

**Full (PDF extraction + semantic search):**
```bash
pip install -r requirements.txt

# For OCR support (scanned PDFs):
# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils
# macOS
brew install tesseract poppler
```

## Usage

### Interactive Mode (recommended)
```bash
python -m filefinder ~/Documents
```

This gives you an interactive prompt:
```
Indexed 4,521 files.
Content extraction running in background...

FileFinder Agent - Interactive Mode
========================================
Commands:
  <query>          Search for files
  open <number>    Open a file from last results
  reveal <number>  Show file in file manager
  stats            Show index statistics
  semantic <query> Use AI semantic search
  type <ext>       Find files by extension
  quit             Exit

FileFinder> find my resume
Results for "find my resume":

  [1] Resume_2024.pdf                        245KB [content matched]
      /home/user/Documents/Resume_2024.pdf
  [2] resume_draft.docx                       52KB [name matched]
      /home/user/Documents/drafts/resume_draft.docx

  2 results. Use 'open <number>' or 'reveal <number>'.

FileFinder> open 1
Opening: /home/user/Documents/Resume_2024.pdf
```

### Single Query
```bash
python -m filefinder ~/Documents "budget report"
```

### Semantic Search (AI-powered)
```bash
python -m filefinder ~/Documents "that paper about neural networks" --semantic
```

### Find by File Type
```bash
python -m filefinder ~/Documents --type pdf
```

### Other Options
```
--limit N       Max results (default: 10)
--stats         Show index statistics
--no-content    Skip content extraction (fast metadata-only mode)
--reindex       Force full reindex
--verbose       Debug logging
```

## Project Structure

```
FileFinder/
├── filefinder/
│   ├── __init__.py     # Package version
│   ├── __main__.py     # python -m entry point
│   ├── agent.py        # Brain: orchestrates indexing + search + file ops
│   ├── cli.py          # Interactive CLI
│   ├── extractor.py    # Tiered text extraction (PDF, DOCX, TXT, code...)
│   ├── scanner.py      # Filesystem walker with security exclusions
│   └── store.py        # SQLite + FTS5 storage layer
├── Test_tranformer_Search.py  # Original prototype
├── requirements.txt
└── README.md
```

## Supported File Types

**Content extraction (Tier 2):**
- Documents: PDF, DOCX, TXT, MD, RST, CSV
- Code: Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, Ruby, PHP, SQL, Shell
- Config: JSON, XML, YAML, TOML, INI, HTML
- All other files are still searchable by filename/metadata (Tier 1)

## Roadmap
- File system watcher for live index updates (watchdog)
- Web UI / Electron desktop app
- Voice command support
- PPTX, XLSX extraction
- Image OCR (find text in screenshots)
- Cross-platform installer

## Contributing
Contributions are welcome! Fork this repository, make your changes, and submit a pull request.

# FileFinder

FileFinder is a smart file search tool that uses **transformer-based semantic matching** to find files using natural language queries. Instead of searching by exact filenames, you describe what you're looking for and FileFinder finds the most relevant documents.

## Features

- **Semantic Search**: Uses sentence-transformers (`all-MiniLM-L6-v2`) to understand the meaning of your query and match it against document contents.
- **Smart PDF Extraction**: Tries fast native text extraction (pdfplumber) first, falls back to OCR (pytesseract) for scanned PDFs.
- **Multi-Format Support**: Searches across PDF, TXT, and DOCX files.
- **Embedding Cache**: Caches computed embeddings to disk so subsequent searches are instant (no re-indexing unless files change).
- **Top-K Results**: Returns multiple ranked results with similarity scores instead of just one match.
- **Interactive Mode**: Run multiple queries without re-indexing each time.
- **CLI Interface**: Full command-line interface with configurable options.

## Installation

**Requirements:** Python 3.8+

```bash
pip install -r requirements.txt
```

For OCR support (scanned PDFs), you also need Tesseract installed:
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler
```

## Usage

### Single Query
```bash
python -m filefinder /path/to/documents "find my assignment"
```

### Interactive Mode (multiple queries, index once)
```bash
python -m filefinder /path/to/documents --interactive
```

### Options
```
python -m filefinder --help

positional arguments:
  directory             Directory to scan for files
  query                 Natural language search query

options:
  --top-k N             Number of results to return (default: 5)
  --threshold SCORE     Minimum similarity score 0.0-1.0 (default: 0.0)
  --model MODEL         Sentence-transformer model name
  --page-limit N        Max PDF pages to extract per file (default: 5)
  --reindex             Force reindexing, ignoring cache
  --interactive         Enter interactive search mode
  --verbose             Enable debug logging
```

### Example Queries
```bash
python -m filefinder ~/Documents "where is my resume"
python -m filefinder ~/Documents "machine learning homework" --top-k 10
python -m filefinder /data "invoice from march" --threshold 0.3
```

## Project Structure

```
FileFinder/
├── filefinder/
│   ├── __init__.py       # Package init
│   ├── __main__.py       # python -m entry point
│   ├── cli.py            # Command-line interface
│   ├── extractor.py      # Text extraction (PDF, TXT, DOCX)
│   ├── indexer.py         # Embedding computation + caching
│   └── searcher.py        # Search engine class
├── Test_tranformer_Search.py  # Original prototype script
├── requirements.txt
└── README.md
```

## How It Works

1. **Scan** - Recursively finds all supported files (PDF, TXT, DOCX) in the target directory.
2. **Extract** - Pulls text from each file. For PDFs, uses pdfplumber for native text extraction; falls back to OCR (pytesseract) for scanned documents.
3. **Encode** - Converts extracted text into vector embeddings using a sentence-transformer model. Results are cached to disk.
4. **Search** - Encodes your query into an embedding and compares it against all document embeddings using cosine similarity. Returns the top-K most relevant files.

## Roadmap
- Fine-tuning transformer models for better file-specific matching
- Voice command support
- Support for more file types (PPTX, XLSX, images with OCR)
- Web UI / desktop app interface
- Cross-platform packaging

## Contributing
Contributions are welcome! Please fork this repository, make your changes, and submit a pull request.

## Acknowledgments
- [Sentence Transformers](https://www.sbert.net/) for the embedding models
- [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF text extraction
- The open-source community for providing the tools and libraries used in this project

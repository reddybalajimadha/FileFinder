"""Tiered text extraction from various file types.

Tier 2 (fast): Native text extraction for PDFs (pdfplumber), TXT, DOCX, etc.
Tier 3 (slow): OCR for scanned PDFs - only used on-demand or in background.

All extraction functions return text or None, never raise.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Extensions that can have text extracted
EXTRACTABLE_EXTENSIONS = {
    ".pdf", ".txt", ".docx", ".md", ".rst", ".csv",
    ".json", ".xml", ".html", ".htm", ".yaml", ".yml",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h",
    ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1",
    ".sql", ".r", ".m", ".swift", ".kt", ".scala",
    ".ini", ".cfg", ".conf", ".toml", ".log",
}


def extract_text(file_path, use_ocr=False, pdf_page_limit=5):
    """Extract text from a file based on its extension.

    Args:
        file_path: Path to the file.
        use_ocr: If True, use OCR for PDFs (Tier 3). Otherwise native only (Tier 2).
        pdf_page_limit: Max pages to extract from PDFs.

    Returns:
        Extracted text string, or None if extraction fails.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_pdf(file_path, use_ocr=use_ocr, page_limit=pdf_page_limit)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext in (".html", ".htm"):
        return _extract_html(file_path)
    elif ext in EXTRACTABLE_EXTENSIONS:
        # All other text-based files
        return _extract_plaintext(file_path)
    else:
        return None


def can_extract(extension):
    """Check if we can extract text from this file type."""
    return extension.lower() in EXTRACTABLE_EXTENSIONS


# --- PDF Extraction ---

def _extract_pdf(file_path, use_ocr=False, page_limit=5):
    """Extract text from PDF: native first, optional OCR fallback."""
    text = _extract_pdf_native(file_path, page_limit)

    if text and len(text.strip()) > 50:
        return text.strip()

    if use_ocr:
        logger.debug("Native extraction insufficient, trying OCR for %s", file_path)
        ocr_text = _extract_pdf_ocr(file_path, page_limit)
        if ocr_text and len(ocr_text.strip()) > 0:
            return ocr_text.strip()

    if text and len(text.strip()) > 0:
        return text.strip()

    return None


def _extract_pdf_native(file_path, page_limit):
    """Fast native text extraction using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:page_limit]:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        logger.debug("pdfplumber not installed, skipping native PDF extraction")
        return None
    except Exception as e:
        logger.debug("Native PDF extraction failed for %s: %s", file_path, e)
        return None


def _extract_pdf_ocr(file_path, page_limit):
    """Slow OCR extraction using pytesseract + pdf2image."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        images = convert_from_path(file_path)
        text_parts = []
        for image in images[:page_limit]:
            page_text = pytesseract.image_to_string(image)
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        logger.debug("pytesseract/pdf2image not installed, OCR unavailable")
        return None
    except Exception as e:
        logger.debug("OCR extraction failed for %s: %s", file_path, e)
        return None


# --- Other formats ---

def _extract_docx(file_path):
    """Extract text from DOCX files."""
    try:
        import docx
        doc = docx.Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs).strip() or None
    except ImportError:
        logger.debug("python-docx not installed, DOCX extraction unavailable")
        return None
    except Exception as e:
        logger.debug("DOCX extraction failed for %s: %s", file_path, e)
        return None


def _extract_html(file_path):
    """Extract text from HTML files, stripping tags."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        # Simple tag stripping without extra dependencies
        import re
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text)
        return text.strip() or None
    except Exception as e:
        logger.debug("HTML extraction failed for %s: %s", file_path, e)
        return None


def _extract_plaintext(file_path, max_bytes=500_000):
    """Extract text from plain text files.

    Reads up to max_bytes to avoid loading huge log files into memory.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(max_bytes)
        return text.strip() or None
    except Exception as e:
        logger.debug("Text extraction failed for %s: %s", file_path, e)
        return None

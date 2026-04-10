"""Text extraction from various file types.

Supports PDF (native text + OCR fallback), TXT, and DOCX files.
"""

import os
import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}


def scan_files(directory):
    """Recursively scan directory for supported file types."""
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    found_files = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                found_files.append(os.path.join(root, fname))

    logger.info("Found %d supported files in %s", len(found_files), directory)
    return sorted(found_files)


def extract_text(file_path, pdf_page_limit=5):
    """Extract text from a file based on its extension.

    For PDFs, tries native text extraction first (pdfplumber), then
    falls back to OCR (pytesseract + pdf2image) if native extraction
    yields little or no text.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_pdf(file_path, page_limit=pdf_page_limit)
    elif ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    else:
        logger.warning("Unsupported file type: %s", file_path)
        return None


def _extract_pdf(file_path, page_limit=5):
    """Extract text from PDF: native first, OCR fallback."""
    text = _extract_pdf_native(file_path, page_limit)

    # If native extraction got meaningful text (>50 chars), use it
    if text and len(text.strip()) > 50:
        logger.debug("Native PDF extraction succeeded for %s", file_path)
        return text.strip()

    # Fall back to OCR
    logger.debug("Falling back to OCR for %s", file_path)
    ocr_text = _extract_pdf_ocr(file_path, page_limit)
    if ocr_text and len(ocr_text.strip()) > 0:
        return ocr_text.strip()

    logger.warning("No text extracted from %s", file_path)
    return None


def _extract_pdf_native(file_path, page_limit):
    """Extract text using pdfplumber (fast, works on text-based PDFs)."""
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages[:page_limit]):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        logger.debug("pdfplumber not installed, skipping native extraction")
        return None
    except Exception as e:
        logger.debug("Native PDF extraction failed for %s: %s", file_path, e)
        return None


def _extract_pdf_ocr(file_path, page_limit):
    """Extract text using OCR (pytesseract + pdf2image). Slower but works on scanned PDFs."""
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
        logger.warning("pytesseract/pdf2image not installed, OCR unavailable")
        return None
    except Exception as e:
        logger.warning("OCR extraction failed for %s: %s", file_path, e)
        return None


def _extract_txt(file_path):
    """Extract text from plain text files."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip() or None
    except Exception as e:
        logger.warning("Failed to read text file %s: %s", file_path, e)
        return None


def _extract_docx(file_path):
    """Extract text from DOCX files using python-docx."""
    try:
        import docx

        doc = docx.Document(file_path)
        text = "\n".join(para.text for para in doc.paragraphs)
        return text.strip() or None
    except ImportError:
        logger.warning("python-docx not installed, DOCX extraction unavailable")
        return None
    except Exception as e:
        logger.warning("Failed to extract DOCX %s: %s", file_path, e)
        return None

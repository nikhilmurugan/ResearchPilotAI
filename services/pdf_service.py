"""
pdf_service.py
--------------
PDF extraction and AI-powered analysis using Ollama.
Optimized for large files: only sends the most relevant text to Ollama.
"""

import os
import logging

from PyPDF2 import PdfReader

from services.ollama_service import ask_ollama, OllamaError

logger = logging.getLogger(__name__)

# Maximum characters sent to Ollama per analysis prompt.
# Tuned to ~3 000 tokens — enough context without hitting timeout.
_MAX_CHARS_PER_PROMPT = 8000

# Maximum total characters extracted from a PDF before trimming.
_MAX_EXTRACT_CHARS = 40000


class PDFError(Exception):
    """Raised when PDF processing fails."""


def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract text from a PDF, returning at most _MAX_EXTRACT_CHARS characters.
    Pages with no extractable text are skipped gracefully.
    """
    if not pdf_path or not os.path.isfile(pdf_path):
        raise PDFError(f"PDF file not found: {pdf_path}")

    if not pdf_path.lower().endswith(".pdf"):
        raise PDFError("Invalid file type. Only PDF files are supported.")

    try:
        reader = PdfReader(pdf_path)
    except Exception as exc:
        raise PDFError(f"Unable to read PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PDFError(f"PDF is encrypted and cannot be opened: {exc}") from exc

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise PDFError("PDF contains no pages.")

    logger.info("Extracting text from %d-page PDF: %s", total_pages, os.path.basename(pdf_path))

    text_parts: list[str] = []
    total_chars = 0

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text()
        except Exception as exc:
            logger.warning("Could not extract page %d: %s", page_num, exc)
            continue

        if not page_text:
            continue

        page_text = page_text.strip()
        remaining = _MAX_EXTRACT_CHARS - total_chars

        if remaining <= 0:
            logger.info("Reached max extract limit at page %d/%d", page_num, total_pages)
            break

        if len(page_text) > remaining:
            page_text = page_text[:remaining]

        text_parts.append(page_text)
        total_chars += len(page_text)

    combined = "\n\n".join(text_parts).strip()
    if not combined:
        raise PDFError("No extractable text found in the PDF.")

    logger.info("Extracted %d characters from %d pages.", total_chars, total_pages)
    return combined


def _smart_truncate(text: str, max_chars: int = _MAX_CHARS_PER_PROMPT) -> str:
    """Truncate text at a sentence boundary where possible."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Try to end at the last sentence boundary
    last_period = max(truncated.rfind(". "), truncated.rfind(".\n"))
    if last_period > max_chars * 0.6:
        return truncated[: last_period + 1].strip()
    return truncated.strip()


def analyze_pdf(content: str) -> dict:
    """
    Run a single Ollama prompt over the PDF content and return
    a dict with 'summary', 'keywords', and 'insights'.

    Only the most relevant slice of text is sent per prompt to keep
    latency low without reducing answer quality.
    """
    if not content or not content.strip():
        raise PDFError("No content provided for analysis.")

    # Use a smart excerpt — first 8 000 chars covers most research abstracts
    excerpt = _smart_truncate(content, _MAX_CHARS_PER_PROMPT)

    system = (
        "You are a senior academic research analyst. "
        "Answer concisely but with scholarly depth. "
        "Do not pad your response with filler text."
    )

    combined_prompt = (
        "Analyze the following research document and provide three sections separated by '===SECTION==='.\n\n"
        "Section 1: A summary in 3-5 concise paragraphs.\n"
        "Section 2: 10-15 important keywords as a comma-separated list.\n"
        "Section 3: Actionable insights covering main thesis, methodology, findings, gaps, and future work.\n\n"
        f"DOCUMENT:\n{excerpt}\n\n"
        "OUTPUT FORMAT EXACTLY LIKE THIS:\n"
        "[Summary text here]\n"
        "===SECTION===\n"
        "[Keywords here]\n"
        "===SECTION===\n"
        "[Insights here]"
    )

    try:
        logger.info("Running PDF analysis — excerpt length: %d chars", len(excerpt))
        # Keep keep_alive loaded by the ask_ollama underlying change
        result = ask_ollama(combined_prompt, system_prompt=system)
        parts = result.split("===SECTION===")
        
        summary = parts[0].strip() if len(parts) > 0 else "Summary not generated."
        keywords = parts[1].strip() if len(parts) > 1 else "Keywords not generated."
        insights = parts[2].strip() if len(parts) > 2 else "Insights not generated."
        
    except OllamaError:
        raise
    except Exception as exc:
        raise PDFError(f"PDF analysis failed: {exc}") from exc

    return {
        "summary":  summary,
        "keywords": keywords,
        "insights": insights,
    }

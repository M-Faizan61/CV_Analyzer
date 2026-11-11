"""Turn an uploaded PDF, DOCX or TXT file into plain text.

A file that cannot be read raises ValueError with a message safe to show the
user. That is a problem with the file, never a judgement about the candidate.
"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from config.settings import MAX_FILE_BYTES, MAX_TEXT_CHARS

MAX_PDF_PAGES = 100
MAX_DOCX_EXPANDED_BYTES = 50 * 1024 * 1024
MIN_TEXT_CHARS = 20


def _read_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")  # older Windows Notepad files


def _read_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("This PDF is password protected. Please provide an unlocked copy.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"This PDF has more than {MAX_PDF_PAGES} pages.")

    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        # A page of images has no readable text, and part of the CV would be missed.
        if len(text.strip()) < 10 and len(page.images) > 0:
            raise ValueError("This PDF contains a scanned page. Please provide a text version of the CV.")
        pages.append(text)
    return "\n".join(pages)


def _read_docx(content: bytes) -> str:
    from docx import Document

    with ZipFile(BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_EXPANDED_BYTES:
            raise ValueError("This document is too large to open safely.")
        if any("vbaProject" in item.filename for item in archive.infolist()):
            raise ValueError("Documents containing macros are not supported.")

    document = Document(BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    table_rows = [" | ".join(cell.text for cell in row.cells) for table in document.tables for row in table.rows]
    return "\n".join(paragraphs + table_rows)


_READERS = {".txt": _read_txt, ".pdf": _read_pdf, ".docx": _read_docx}


def read_document(name: str, content: bytes) -> str:
    """Return the text of a file, or raise ValueError with a readable message."""
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("The file must not be empty and must be 10 MB or smaller.")

    reader = _READERS.get(Path(name).suffix.lower())
    if reader is None:
        raise ValueError("Supported file types are PDF, DOCX and TXT.")

    try:
        text = reader(content)
    except ValueError:
        raise
    except Exception as error:  # the PDF and DOCX libraries raise many private error types
        raise ValueError("This file could not be read. It may be damaged.") from error

    if len(text.strip()) < MIN_TEXT_CHARS:
        raise ValueError("This file has too little readable text. It may be a scanned image.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("This file is too long to process.")
    return text

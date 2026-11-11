from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfWriter

from services.document_reader import read_document


def test_docx_tables_and_paragraphs():
    document = Document()
    document.add_paragraph("Fictional candidate software engineer")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Skills: SQL, Python"
    data = BytesIO()
    document.save(data)
    assert "Skills: SQL, Python" in read_document("cv.docx", data.getvalue())


def test_older_windows_text_files_can_be_read():
    assert "Café" in read_document("cv.txt", "Café owner with long experience".encode("cp1252"))


def test_blank_pdf_is_reported():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    data = BytesIO()
    writer.write(data)
    with pytest.raises(ValueError, match="too little readable text"):
        read_document("cv.pdf", data.getvalue())


@pytest.mark.parametrize("name,data", [("cv.exe", b"x" * 100), ("cv.pdf", b"invalid"), ("cv.txt", b""), ("cv.txt", b"x" * (10 * 1024 * 1024 + 1))])
def test_bad_files_give_a_readable_error(name, data):
    with pytest.raises(ValueError):
        read_document(name, data)

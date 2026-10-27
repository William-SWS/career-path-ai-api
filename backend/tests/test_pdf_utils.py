import asyncio
import io

import pytest
from fastapi import UploadFile
from PyPDF2 import PdfWriter

from app.core.exceptions import ValidationException
from app.utils.pdf_utils import check_pdf


def _upload(content: bytes, filename: str = "cv.pdf") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


def _blank_pdf(password: str | None = None) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _pdf_with_text(text: str) -> bytes:
    """PDF mínimo de uma página, com xref calculado."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref_at = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_at,
    )
    return body


def _check(upload):
    return asyncio.run(check_pdf(upload))


@pytest.mark.parametrize(
    "upload, code",
    [
        (_upload(b"%PDF", filename="cv.docx"), "invalid_file_type"),
        (_upload(b""), "empty_file"),
        (_upload(b"not really a pdf"), "unreadable_pdf"),
        (_upload(_blank_pdf(password="secret")), "encrypted_pdf"),
        (_upload(_blank_pdf()), "pdf_without_text"),
    ],
    ids=["wrong-extension", "empty", "corrupted", "encrypted", "no-text"],
)
def test_unusable_pdf_is_validation_error(upload, code):
    with pytest.raises(ValidationException) as exc_info:
        _check(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == code


def test_extracts_text_from_valid_pdf():
    assert "Python developer" in _check(_upload(_pdf_with_text("Python developer")))

from fastapi import UploadFile
from PyPDF2 import PdfReader
from PyPDF2.errors import PyPdfError
import io

from app.core.exceptions import ValidationException

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 30


async def check_pdf(file: UploadFile) -> str:
    """Extrai o texto de um PDF enviado; levanta ValidationException se o arquivo for inutilizável."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise ValidationException("O arquivo deve ser um PDF", code="invalid_file_type")

    # Lê um byte a mais que o limite só para saber se o arquivo o ultrapassa.
    file_contents = await file.read(MAX_PDF_BYTES + 1)
    if len(file_contents) > MAX_PDF_BYTES:
        raise ValidationException(
            f"O PDF deve ter no máximo {MAX_PDF_BYTES // (1024 * 1024)} MB", code="file_too_large"
        )

    if len(file_contents) == 0:
        raise ValidationException("O arquivo está vazio", code="empty_file")

    try:
        reader = PdfReader(io.BytesIO(file_contents))

        if reader.is_encrypted:
            raise ValidationException(
                "PDF criptografado não é suportado", code="encrypted_pdf"
            )

        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValidationException(
                f"O PDF deve ter no máximo {MAX_PDF_PAGES} páginas", code="too_many_pages"
            )

        text = "".join(
            f"{page_text}\n"
            for page_text in (page.extract_text() for page in reader.pages)
            if page_text
        )
    except PyPdfError:
        raise ValidationException("Não foi possível ler o PDF", code="unreadable_pdf")

    if not text.strip():
        raise ValidationException(
            "Nenhum texto foi encontrado no PDF", code="pdf_without_text"
        )

    return text

from fastapi import UploadFile
from PyPDF2 import PdfReader
from PyPDF2.errors import PyPdfError
import io

from app.core.exceptions import ValidationException


async def check_pdf(file: UploadFile) -> str:
    """Extrai o texto de um PDF enviado; levanta ValidationException se o arquivo for inutilizável."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise ValidationException("O arquivo deve ser um PDF", code="invalid_file_type")

    file_contents = await file.read()

    if len(file_contents) == 0:
        raise ValidationException("O arquivo está vazio", code="empty_file")

    try:
        reader = PdfReader(io.BytesIO(file_contents))

        if reader.is_encrypted:
            raise ValidationException(
                "PDF criptografado não é suportado", code="encrypted_pdf"
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

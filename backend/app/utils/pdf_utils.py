from fastapi import UploadFile, HTTPException
from PyPDF2 import PdfReader
import io

from app.core.logging_config import logger


async def check_pdf(file: UploadFile) -> str:
    try:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="O arquivo deve ser um PDF"
            )
        
        file_contents = await file.read()

        if len(file_contents) == 0:
            raise ValueError("O arquivo está vazio")
        
        pdf_file = io.BytesIO(file_contents)
        reader = PdfReader(pdf_file)

        if reader.is_encrypted:
            raise ValueError("PDF criptografado não é suportado")
        
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            raise ValueError("Nenhum texto foi encontrado no PDF")
        
        return text
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Erro ao processar o PDF")
        raise HTTPException(
                status_code=500,
                detail="Erro interno ao checar o PDF",
            )

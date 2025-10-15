from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.parser import extract_text_from_file
from app.core.embeddings import document_index
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith(('.txt', '.docx', '.pdf', '.xlsx')):
            raise HTTPException(status_code=400, detail="Неподдерживаемый формат")

        document_data = await extract_text_from_file(file)
        document_index.add_documents([document_data])
        document_index.build_index()

        return {
            "filename": file.filename,
            "characters": len(document_data["text"]),
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
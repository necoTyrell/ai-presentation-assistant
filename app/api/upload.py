from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.parser import extract_text_from_file
from app.core.embeddings import document_index
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """Загрузка и индексация одного файла"""
    try:
        # Проверяем тип файла
        if not file.filename.lower().endswith(('.txt', '.docx', '.pdf', '.xlsx')):
            raise HTTPException(
                status_code=400,
                detail="Поддерживаются только файлы: .txt, .docx, .pdf, .xlsx"
            )

        logger.info(f"Обработка файла: {file.filename}")

        # Извлекаем данные из файла
        document_data = await extract_text_from_file(file)

        # Добавляем в индекс
        document_index.add_documents([document_data])

        # Перестраиваем индекс (можно оптимизировать - перестраивать не каждый раз)
        document_index.build_index()

        stats = document_index.get_stats()

        return {
            "filename": file.filename,
            "characters": len(document_data["text"]),
            "tables_found": len(document_data["tables"]),
            "preview": document_data["text"][:500] + "..." if len(document_data["text"]) > 500 else document_data[
                "text"],
            "status": "document_indexed",
            "index_stats": stats
        }

    except Exception as e:
        logger.error(f"Ошибка обработки файла {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/multiple")
async def upload_multiple_files(files: list[UploadFile] = File(...)):
    """Загрузка нескольких файлов"""
    results = []
    successful_uploads = 0

    for file in files:
        try:
            result = await upload_file(file)
            results.append(result)
            successful_uploads += 1
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
                "status": "error"
            })

    # Перестраиваем индекс после загрузки всех файлов
    if successful_uploads > 0:
        document_index.build_index()

    return {
        "results": results,
        "successful_uploads": successful_uploads,
        "total_files": len(files),
        "index_stats": document_index.get_stats()
    }


@router.get("/stats")
async def get_upload_stats():
    """Статистика загруженных документов"""
    return {
        "status": "success",
        "index_stats": document_index.get_stats()
    }


@router.delete("/clear")
async def clear_documents():
    """Очистка всех документов из индекса"""
    document_index.clear()
    return {
        "status": "success",
        "message": "Все документы удалены из индекса"
    }


@router.post("/search-test")
async def test_search(query: str, k: int = 3):
    """Тестовый поиск по индексу"""
    try:
        if not document_index.is_built:
            raise HTTPException(status_code=400, detail="Индекс не построен. Сначала загрузите документы.")

        results = document_index.search(query, k)

        formatted_results = []
        for content, content_type, source in results:
            formatted_results.append({
                "content": content[:200] + "..." if len(content) > 200 else content,
                "type": content_type,
                "source": source,
                "content_length": len(content)
            })

        return {
            "query": query,
            "results_count": len(results),
            "results": formatted_results
        }

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        raise HTTPException(status_code=500, detail=str(e))
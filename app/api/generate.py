from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io
import logging
import uuid
from datetime import datetime

from app.api.presentation_templates import templates_store
from app.core.embeddings import document_index
from app.core.llm_generator import content_generator
from app.core.pptx_builder import PresentationBuilder

router = APIRouter()
logger = logging.getLogger(__name__)

generation_status = {}


class GenerationRequest(BaseModel):
    audience: str = "инвесторы"
    presentation_type: str = "standard"
    template_id: Optional[str] = None


class GenerationResponse(BaseModel):
    job_id: str
    status: str
    message: str


def _get_slides_structure():
    return [
        {"type": "title", "title": "Инвестиционная презентация"},
        {"type": "problem", "title": "Проблема"},
        {"type": "solution", "title": "Решение"},
        {"type": "market", "title": "Рынок и возможности"},
        {"type": "finance", "title": "Финансовые показатели"},
        {"type": "team", "title": "Команда"},
        {"type": "summary", "title": "Резюме"}
    ]


def _search_relevant_context(slide_type: str, title: str) -> str:
    search_queries = {
        "title": "название проект продукт",
        "problem": "проблема задача вызов",
        "solution": "решение продукт технология",
        "market": "рынок объем аудитория тренды",
        "finance": "финансы выручка инвестиции",
        "team": "команда опыт специалисты",
        "summary": "резюме выводы итоги"
    }

    query = search_queries.get(slide_type, title)
    results = document_index.search(query, k=2)  # Берем больше результатов

    if results:
        # Объединяем контекст из нескольких результатов
        context_parts = []
        for content, content_type, source in results[:2]:
            if content and len(content) > 10:
                context_parts.append(content[:150])

        if context_parts:
            return " | ".join(context_parts)

    return "Проект представляет инновационное решение"


def _generate_presentation_task(job_id: str, request: GenerationRequest):
    try:
        logger.info(f"🚀 Начата генерация презентации для job {job_id}")

        generation_status[job_id].update({"status": "processing", "progress": 10})

        # Создаем билдер
        if request.template_id and request.template_id in templates_store:
            template_info = templates_store[request.template_id]
            template_path = template_info["file_path"]
            builder = PresentationBuilder(template_path)
            logger.info(f"📁 Используется шаблон: {template_info['name']}")
        else:
            builder = PresentationBuilder()
            logger.info("📁 Используется стандартный шаблон")

        slides_structure = _get_slides_structure()
        generation_status[job_id]["slides_generated"] = []

        # Генерируем каждый слайд
        for i, slide_spec in enumerate(slides_structure):
            progress = 10 + int((i / len(slides_structure)) * 80)
            generation_status[job_id]["progress"] = progress

            slide_type = slide_spec["type"]
            slide_title = slide_spec["title"]
            context = _search_relevant_context(slide_type, slide_title)

            logger.info(f"📝 Генерация слайда {i + 1}/{len(slides_structure)}: {slide_title}")

            # Генерируем контент
            generation_result = content_generator.generate_slide_content(
                slide_type, context, request.audience
            )

            # Создаем слайд
            builder.add_slide(slide_type, slide_title, generation_result["content"])
            logger.info(f"✅ Создан слайд: {slide_title}")

            generation_status[job_id]["slides_generated"].append({
                "slide_type": slide_type,
                "title": slide_title,
                "content": generation_result["content"],
                "status": "success"
            })

        # Сохраняем
        generation_status[job_id]["progress"] = 95
        presentation_bytes = builder.save_to_bytes()

        generation_status[job_id].update({
            "status": "completed",
            "progress": 100,
            "presentation_data": presentation_bytes.getvalue(),
            "slides_count": builder.get_slide_count(),
            "presentation_filename": f"presentation_{job_id[:8]}.pptx"
        })

        logger.info(f"🎉 Презентация успешно сгенерирована! Слайдов: {builder.get_slide_count()}")

    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        generation_status[job_id].update({
            "status": "failed",
            "error_message": str(e)
        })


@router.post("/presentation", response_model=GenerationResponse)
async def generate_presentation(request: GenerationRequest, background_tasks: BackgroundTasks):
    if not document_index.documents:
        raise HTTPException(status_code=400, detail="Сначала загрузите документы")

    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    generation_status[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "slides_generated": [],
        "created_at": now,
        "updated_at": now,
        "presentation_data": None
    }

    background_tasks.add_task(_generate_presentation_task, job_id, request)

    return GenerationResponse(
        job_id=job_id,
        status="pending",
        message="Генерация запущена"
    )


@router.get("/download/{job_id}")
async def download_presentation(job_id: str):
    if job_id not in generation_status:
        raise HTTPException(status_code=404, detail="Job not found")

    status_data = generation_status[job_id]

    if status_data["status"] != "completed":
        raise HTTPException(status_code=400, detail="Presentation not ready")

    presentation_bytes = io.BytesIO(status_data["presentation_data"])
    filename = status_data["presentation_filename"]

    return StreamingResponse(
        presentation_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/status/{job_id}")
async def get_generation_status(job_id: str):
    if job_id not in generation_status:
        raise HTTPException(status_code=404, detail="Job not found")

    status_data = generation_status[job_id]

    return {
        "job_id": job_id,
        "status": status_data["status"],
        "progress": status_data["progress"],
        "slides_count": status_data.get("slides_count", 0)
    }


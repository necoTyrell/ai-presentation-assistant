from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import io
import logging
import uuid
from datetime import datetime

from app.api.presentation_templates import templates_store
from app.core.powerpoint_templates.builder import TemplatePresentationBuilder
from app.core.pptx_builder import PresentationBuilder
from app.core.embeddings import document_index
from app.core.llm_generator import content_generator
from tests.test_prompts import get_slide_prompt

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for generation status
generation_status = {}


# ========== MODELS ==========
class GenerationTestRequest(BaseModel):
    slide_type: str
    context: str
    audience: str = "инвесторы"


class GenerationTestResponse(BaseModel):
    slide_type: str
    audience: str
    prompt_used: str
    generation_result: Dict[str, Any]
    model_health: Dict[str, Any]


class BatchTestRequest(BaseModel):
    slide_type: str
    context: str
    audience: str = "инвесторы"


class ModelHealthResponse(BaseModel):
    status: str
    model: str
    test_generation: Optional[bool] = None
    error: Optional[str] = None


class GenerationRequest(BaseModel):
    audience: str = "инвесторы"
    presentation_type: str = "standard"
    template_id: Optional[str] = None
    custom_slides: Optional[List[str]] = None
    title: Optional[str] = None


class GenerationResponse(BaseModel):
    job_id: str
    status: str
    message: str
    estimated_time: Optional[int] = None


class SlideContent(BaseModel):
    slide_type: str
    title: str
    content: str
    status: str


class PresentationStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    slides_generated: List[SlideContent]
    slides_count: Optional[int] = None  # ← ДОБАВИТЬ ЭТО
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


# ========== LLM ENDPOINTS ==========
@router.post("/test-llm", response_model=GenerationTestResponse)
async def test_llm_generation(request: GenerationTestRequest):
    """Тестовый эндпоинт для проверки генерации контента LLM"""
    try:
        # Проверяем здоровье модели
        health = content_generator.health_check()
        if health["status"] not in ["healthy", "loaded"]:
            raise HTTPException(status_code=503, detail=f"Модель не готова: {health}")

        # Генерируем контент
        result = content_generator.generate_slide_content(
            request.slide_type,
            request.context,
            request.audience
        )

        # Получаем промпт для отладки
        prompt_used = get_slide_prompt(request.slide_type, request.context, request.audience)

        return GenerationTestResponse(
            slide_type=request.slide_type,
            audience=request.audience,
            prompt_used=prompt_used[:500] + "..." if len(prompt_used) > 500 else prompt_used,
            generation_result=result,
            model_health=health
        )

    except Exception as e:
        logger.error(f"Ошибка тестовой генерации: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-status", response_model=ModelHealthResponse)
async def get_llm_status():
    """Статус LLM модели"""
    return content_generator.health_check()


@router.post("/batch-test-llm")
async def batch_test_llm_generation(test_cases: List[BatchTestRequest]):
    """Пакетное тестирование генерации LLM"""
    results = {}

    for i, test_case in enumerate(test_cases):
        result = content_generator.generate_slide_content(
            test_case.slide_type,
            test_case.context,
            test_case.audience
        )
        results[f"test_{i}"] = {
            "spec": test_case.model_dump(),
            "result": result
        }

    return {"results": results}


@router.get("/prompt-examples")
async def get_prompt_examples():
    """Возвращает примеры промптов для разных типов слайдов"""
    example_context = "Проект разработки AI-ассистента для автоматизации создания инвестиционных презентаций. Рынок: $500 млн в год. Проблема: команды тратят 40+ часов на подготовку каждой презентации."
    example_audience = "инвесторы"

    slide_types = ["title", "problem", "solution", "market", "team", "finance", "summary"]

    examples = {}
    for slide_type in slide_types:
        prompt = get_slide_prompt(slide_type, example_context, example_audience)
        examples[slide_type] = {
            "prompt": prompt,
            "description": f"Промпт для слайда '{slide_type}'"
        }

    return examples


# ========== PRESENTATION GENERATION ENDPOINTS ==========
def _get_slides_structure(presentation_type: str, custom_slides: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Возвращает структуру слайдов в зависимости от типа презентации"""

    standard_structure = [
        {"type": "title", "title": "Инвестиционная презентация"},
        {"type": "problem", "title": "Проблема"},
        {"type": "solution", "title": "Решение"},
        {"type": "market", "title": "Рынок и возможности"},
        {"type": "finance", "title": "Финансовые показатели"},
        {"type": "team", "title": "Команда"},
        {"type": "summary", "title": "Резюме и next steps"}
    ]

    minimal_structure = [
        {"type": "title", "title": "Инвестиционная презентация"},
        {"type": "problem", "title": "Проблема"},
        {"type": "solution", "title": "Решение"},
        {"type": "finance", "title": "Финансовые показатели"},
        {"type": "summary", "title": "Резюме"}
    ]

    detailed_structure = standard_structure + [
        {"type": "technology", "title": "Технологии"},
        {"type": "roadmap", "title": "Дорожная карта"},
        {"type": "risks", "title": "Риски и mitigation"}
    ]

    structures = {
        "minimal": minimal_structure,
        "standard": standard_structure,
        "detailed": detailed_structure
    }

    return structures.get(presentation_type, standard_structure)


def _search_relevant_context(slide_type: str, title: str) -> str:
    """Ищет релевантный контекст для слайда в загруженных документах"""
    search_queries = {
        "title": "название проекта продукт компания",
        "problem": "проблема задача боль потребность",
        "solution": "решение продукт технология преимущества уникальность",
        "market": "рынок объем тренды конкуренты аудитория",
        "finance": "финансы выручка прибыль инвестиции окупаемость EBITDA",
        "team": "команда опыт экспертиза компетенции участники",
        "technology": "технологии стек разработка архитектура",
        "roadmap": "дорожная карта этапы план сроки milestones",
        "risks": "риски проблемы угрозы mitigation",
        "summary": "резюме выводы итоги рекомендации",
        "custom": title
    }

    query = search_queries.get(slide_type, title)
    results = document_index.search(query, k=2)  # ← УМЕНЬШИЛИ до 2 результатов

    context_parts = []
    for content, content_type, source in results:
        # ОГРАНИЧИВАЕМ длину каждого результата
        shortened_content = content[:300] + "..." if len(content) > 300 else content
        context_parts.append(f"[{content_type} из {source}]: {shortened_content}")

    # ОБЩЕЕ ОГРАНИЧЕНИЕ КОНТЕКСТА
    full_context = "\n".join(context_parts) if context_parts else "Информация не найдена в загруженных документах"
    return full_context[:800]


def _generate_presentation_task(job_id: str, request: GenerationRequest):
    """Фоновая задача генерации презентации"""
    try:
        logger.info(f"Starting presentation generation for job {job_id}")

        # Обновляем статус
        generation_status[job_id].update({
            "status": "processing",
            "progress": 10,
            "updated_at": datetime.now().isoformat()
        })

        # Проверяем что документы загружены
        if len(document_index.documents) == 0:
            generation_status[job_id].update({
                "status": "failed",
                "error_message": "Сначала загрузите документы через /upload",
                "updated_at": datetime.now().isoformat()
            })
            return

        # Получаем структуру слайдов
        slides_structure = _get_slides_structure(
            request.presentation_type,
            request.custom_slides
        )

        # Создаем билдер - с шаблоном или без
        if request.template_id and request.template_id in templates_store:
            template_info = templates_store[request.template_id]
            builder = TemplatePresentationBuilder(template_info["file_path"])
            generation_status[job_id]["template_used"] = template_info["name"]
            logger.info(f"Используется шаблон: {template_info['name']}")
        else:
            builder = PresentationBuilder()
            generation_status[job_id]["template_used"] = "Стандартный"
            logger.info("Используется стандартный билдер")

        generation_status[job_id]["slides_generated"] = []
        total_slides = len(slides_structure)

        # Генерируем контент для каждого слайда
        for i, slide_spec in enumerate(slides_structure):
            slide_type = slide_spec["type"]
            slide_title = slide_spec["title"]

            # Обновляем прогресс
            progress = 10 + int((i / total_slides) * 80)
            generation_status[job_id]["progress"] = progress

            # Ищем релевантный контекст
            context = _search_relevant_context(slide_type, slide_title)
            logger.debug(f"Для слайда '{slide_title}' найден контекст: {context[:100]}...")

            # Генерируем контент через LLM
            generation_result = content_generator.generate_slide_content(
                slide_type, context, request.audience
            )

            logger.debug(f"LLM сгенерировал контент: {generation_result['content'][:100]}...")

            # Сохраняем результат генерации
            slide_content = SlideContent(
                slide_type=slide_type,
                title=slide_title,
                content=generation_result["content"],
                status=generation_result["status"]
            )

            generation_status[job_id]["slides_generated"].append(slide_content)

            # Добавляем слайд используя шаблон
            if hasattr(builder, 'add_slide_from_template'):
                # Используем шаблонный билдер
                builder.add_slide_from_template(
                    slide_type=slide_type,
                    title=slide_title,
                    content=generation_result["content"],
                    layout_index=i,  # Передаем индекс для циклического использования макетов
                    audience=request.audience
                )
            else:
                # Используем стандартный билдер
                if slide_type == "title":
                    builder.add_title_slide(
                        title=slide_title,
                        subtitle=f"Аудитория: {request.audience}\nСгенерировано AI Assistant"
                    )
                else:
                    builder.add_content_slide(
                        title=slide_title,
                        content=generation_result["content"],
                        content_type="bullets" if slide_type in ["solution", "summary"] else "text"
                    )

            logger.info(f"Сгенерирован слайд {i + 1}/{total_slides}: {slide_title}")

        # Сохраняем презентацию
        generation_status[job_id]["progress"] = 95
        presentation_bytes = builder.save_to_bytes()

        # Сохраняем файл в памяти
        generation_status[job_id]["presentation_data"] = presentation_bytes.getvalue()
        template_suffix = f"_{request.template_id[:8]}" if request.template_id else ""
        generation_status[job_id]["presentation_filename"] = f"presentation{template_suffix}_{job_id[:8]}.pptx"
        generation_status[job_id]["slides_count"] = builder.get_slide_count()

        # Финальный статус
        generation_status[job_id].update({
            "status": "completed",
            "progress": 100,
            "download_url": f"/generate/download/{job_id}",
            "updated_at": datetime.now().isoformat()
        })

        logger.info(f"Презентация успешно сгенерирована. Слайдов: {builder.get_slide_count()}")

    except Exception as e:
        logger.error(f"Ошибка генерации презентации: {e}")
        generation_status[job_id].update({
            "status": "failed",
            "error_message": str(e),
            "updated_at": datetime.now().isoformat()
        })


@router.post("/presentation", response_model=GenerationResponse)
async def generate_presentation(
        request: GenerationRequest,
        background_tasks: BackgroundTasks
):
    """Запускает генерацию презентации"""

    # Проверяем что модель готова
    model_health = content_generator.health_check()
    if model_health["status"] not in ["healthy", "loaded"]:
        raise HTTPException(
            status_code=503,
            detail=f"LLM модель не готова: {model_health}"
        )

    # Проверяем что документы загружены
    if not document_index.documents:
        raise HTTPException(
            status_code=400,
            detail="Сначала загрузите документы через /upload endpoint"
        )

    # Создаем job ID
    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    # Инициализируем статус
    generation_status[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "slides_generated": [],
        "download_url": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
        "presentation_data": None,
        "presentation_filename": None
    }

    # Запускаем фоновую задачу
    background_tasks.add_task(_generate_presentation_task, job_id, request)

    return GenerationResponse(
        job_id=job_id,
        status="pending",
        message="Генерация презентации запущена",
        estimated_time=len(document_index.documents) * 10
    )


@router.get("/status/{job_id}", response_model=PresentationStatusResponse)
async def get_generation_status(job_id: str):
    if job_id not in generation_status:
        raise HTTPException(status_code=404, detail="Job not found")

    status_data = generation_status[job_id]

    return PresentationStatusResponse(
        job_id=status_data["job_id"],
        status=status_data["status"],
        progress=status_data["progress"],
        slides_generated=status_data["slides_generated"],
        slides_count=status_data.get("slides_count"),  # ← ДОБАВИТЬ
        download_url=status_data["download_url"],
        error_message=status_data.get("error_message"),
        created_at=status_data["created_at"],
        updated_at=status_data["updated_at"]
    )


@router.get("/download/{job_id}")
async def download_presentation(job_id: str):
    """Скачивает сгенерированную презентацию"""

    if job_id not in generation_status:
        raise HTTPException(status_code=404, detail="Job not found")

    status_data = generation_status[job_id]

    if status_data["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Presentation not ready. Current status: {status_data['status']}"
        )

    if not status_data.get("presentation_data"):
        raise HTTPException(status_code=404, detail="Presentation data not found")

    presentation_bytes = io.BytesIO(status_data["presentation_data"])
    filename = status_data["presentation_filename"]

    return StreamingResponse(
        presentation_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/jobs")
async def list_jobs():
    """Список всех jobs"""
    return {
        "jobs": list(generation_status.keys()),
        "total": len(generation_status)
    }


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Удаляет job из памяти"""
    if job_id in generation_status:
        del generation_status[job_id]
        return {"message": f"Job {job_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/ready")
async def check_generation_ready():
    """Проверяет готовность системы к генерации"""
    model_health = content_generator.health_check()

    # Безопасная проверка document_index
    try:
        documents_loaded = len(document_index.documents) > 0
        documents_count = len(document_index.documents)
        index_built = document_index.is_built
    except Exception as e:
        logger.error(f"Error checking document index: {e}")
        documents_loaded = False
        documents_count = 0
        index_built = False

    return {
        "ready": model_health["status"] in ["healthy", "loaded"] and documents_loaded,
        "model_status": model_health,
        "documents_loaded": documents_loaded,
        "documents_count": documents_count,
        "index_built": index_built
    }
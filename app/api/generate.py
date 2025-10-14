from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from app.core.llm_generator import content_generator
from tests.test_prompts import get_slide_prompt

router = APIRouter()
logger = logging.getLogger(__name__)


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


class BatchTestResponse(BaseModel):
    results: Dict[str, Any]


class ModelHealthResponse(BaseModel):
    status: str
    model: str
    test_generation: Optional[bool] = None
    error: Optional[str] = None


@router.post("/test-generate", response_model=GenerationTestResponse)
async def test_generation(request: GenerationTestRequest):
    """Тестовый эндпоинт для проверки генерации контента"""
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


@router.get("/model-status", response_model=ModelHealthResponse)
async def get_model_status():
    """Статус LLM модели"""
    return content_generator.health_check()


@router.post("/batch-test")
async def batch_test_generation(test_cases: List[BatchTestRequest]):
    """Пакетное тестирование генерации"""
    results = {}

    for i, test_case in enumerate(test_cases):
        result = content_generator.generate_slide_content(
            test_case.slide_type,
            test_case.context,
            test_case.audience
        )
        results[f"test_{i}"] = {
            "spec": test_case.dict(),
            "result": result
        }

    return BatchTestResponse(results=results)


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
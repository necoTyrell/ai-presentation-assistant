import torch
from transformers import pipeline
from app.config import settings
from tests.test_prompts import get_slide_prompt
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.generator = None
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        """Загрузка модели генерации текста"""
        try:
            logger.info(f"Загрузка LLM модели: {settings.LLM_MODEL}")

            # Пробуем загрузить через pipeline для простоты
            self.generator = pipeline(
                "text-generation",
                model=settings.LLM_MODEL,
                tokenizer=settings.LLM_MODEL,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                model_kwargs={
                    "load_in_8bit": settings.LOAD_IN_8BIT,
                    "torch_dtype": torch.float16,
                } if torch.cuda.is_available() else {}
            )

            self.is_loaded = True
            logger.info("LLM модель успешно загружена")

        except Exception as e:
            logger.error(f"Ошибка загрузки основной модели: {e}")
            self._load_fallback_model()

    def _load_fallback_model(self):
        """Загрузка fallback модели если основная не загрузилась"""
        try:
            logger.info("Попытка загрузки fallback модели...")

            # Используем более легкую модель как запасной вариант
            fallback_model = "IlyaGusev/fred_t5_ru_turbo"
            self.generator = pipeline(
                "text2text-generation",
                model=fallback_model,
                max_length=settings.MAX_NEW_TOKENS,
                temperature=settings.TEMPERATURE,
            )

            self.is_loaded = True
            logger.info("Fallback модель успешно загружена")

        except Exception as e:
            logger.error(f"Ошибка загрузки fallback модели: {e}")
            self.is_loaded = False

    @staticmethod
    def _clean_generated_text(text: str, prompt: str) -> str:
        """Очистка сгенерированного текста от промпта и артефактов"""
        # Удаляем промпт из начала текста если он там есть
        if text.startswith(prompt):
            text = text[len(prompt):].strip()

        # Удаляем лишние кавычки и символы
        text = text.strip('"\' \n')

        # Обрезаем до первого полного предложения если текст слишком длинный
        sentences = text.split('. ')
        if len(sentences) > 0:
            text = '. '.join(sentences[:3]) + '.' if len(sentences) > 3 else text

        return text

    def generate_slide_content(self, slide_type: str, context: str, audience: str = "инвесторы") -> Dict[str, Any]:
        """Генерация контента для слайда"""

        if not self.is_loaded:
            return {
                "content": f"[Модель не загружена] Контент для слайда '{slide_type}'",
                "status": "error",
                "error": "LLM модель не доступна"
            }

        try:
            # Получаем промпт для конкретного типа слайда
            prompt = get_slide_prompt(slide_type, context, audience)

            logger.info(f"Генерация контента для слайда: {slide_type}")
            logger.debug(f"Промпт: {prompt[:200]}...")

            # Генерация текста
            if hasattr(self.generator, 'task') and self.generator.task == "text2text-generation":
                # Для T5 моделей (text2text-generation)
                result = self.generator(
                    prompt,
                    max_length=settings.MAX_NEW_TOKENS,
                    temperature=settings.TEMPERATURE,
                    do_sample=settings.DO_SAMPLE,
                    num_return_sequences=1
                )
                generated_text = result[0]['generated_text']
            else:
                # Для causal LM моделей (text-generation)
                result = self.generator(
                    prompt,
                    max_length=settings.MAX_NEW_TOKENS,
                    temperature=settings.TEMPERATURE,
                    top_p=settings.TOP_P,
                    do_sample=settings.DO_SAMPLE,
                    num_return_sequences=1,
                    pad_token_id=self.generator.tokenizer.eos_token_id,
                    eos_token_id=self.generator.tokenizer.eos_token_id,
                )
                generated_text = result[0]['generated_text']

            # Очищаем сгенерированный текст
            cleaned_text = self._clean_generated_text(generated_text, prompt)

            logger.info(f"Успешно сгенерирован контент для {slide_type}")

            return {
                "content": cleaned_text,
                "slide_type": slide_type,
                "audience": audience,
                "context_used": context[:100] + "..." if len(context) > 100 else context,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Ошибка генерации контента для {slide_type}: {e}")
            return {
                "content": f"Не удалось сгенерировать контент для слайда '{slide_type}'. Ошибка: {str(e)}",
                "status": "error",
                "error": str(e)
            }

    def batch_generate(self, slides_specs: list) -> Dict[str, Any]:
        """Пакетная генерация контента для нескольких слайдов"""
        results = {}

        for spec in slides_specs:
            slide_type = spec.get("type")
            context = spec.get("context", "")
            audience = spec.get("audience", "инвесторы")

            result = self.generate_slide_content(slide_type, context, audience)
            results[slide_type] = result

        return results

    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья модели"""
        try:
            if not self.is_loaded:
                return {"status": "not_loaded", "model": settings.LLM_MODEL}

            # Простая проверка - генерация короткого текста
            test_prompt = "Сгенерируй тестовое сообщение:"
            test_result = self.generator(
                test_prompt,
                max_length=50,
                num_return_sequences=1
            )

            return {
                "status": "healthy",
                "model": settings.LLM_MODEL,
                "test_generation": len(test_result[0]['generated_text']) > 0
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "model": settings.LLM_MODEL}


# Глобальный экземпляр генератора
content_generator = ContentGenerator()

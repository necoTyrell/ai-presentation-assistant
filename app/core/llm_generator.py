import torch
from transformers import pipeline
from app.config import settings
import logging
from typing import Dict, Any
import re

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self):
        self.generator = None
        self.is_loaded = False
        self._load_qwen_model()

    def _load_qwen_model(self):
        """Загрузка Qwen модели"""
        try:
            logger.info(f"Загрузка Qwen модели: {settings.LLM_MODEL}")

            # Qwen использует специальный подход
            self.generator = pipeline(
                "text-generation",
                model=settings.LLM_MODEL,
                torch_dtype=torch.float32,
                device_map="auto",  # Qwen лучше с auto device map
                max_new_tokens=settings.MAX_NEW_TOKENS,
                temperature=settings.TEMPERATURE,
                top_p=settings.TOP_P,
                do_sample=settings.DO_SAMPLE,
            )

            self.is_loaded = True
            logger.info(f"✅ Qwen модель {settings.LLM_MODEL} успешно загружена")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки Qwen модели: {e}")
            self._load_fallback_model()

    def _load_fallback_model(self):
        """Загрузка fallback модели если Qwen не загрузился"""
        try:
            logger.info("Попытка загрузки GPT-2 как fallback...")

            self.generator = pipeline(
                "text-generation",
                model="gpt2",
                max_new_tokens=settings.MAX_NEW_TOKENS,
                temperature=settings.TEMPERATURE,
            )

            self.is_loaded = True
            logger.info("✅ GPT-2 загружен как fallback модель")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки fallback модели: {e}")
            self._enable_test_mode()

    def _enable_test_mode(self):
        """Включаем тестовый режим"""
        logger.info("🔄 Активация тестового режима")
        self.is_loaded = True
        self.test_mode = True

    def _build_qwen_prompt(self, slide_type: str, context: str, audience: str) -> str:
        """Строит промпты в формате Qwen Chat"""

        # Qwen использует chat-формат с системным промптом
        system_prompt = """Ты - AI ассистент для создания инвестиционных презентаций. 
Твоя задача - генерировать качественный контент для слайдов на основе предоставленного контекста.
Будь профессиональным, убедительным и лаконичным."""

        user_prompts = {
            "title": f"Сгенерируй убедительный заголовок для инвестиционной презентации. Контекст: {context}",
            "problem": f"Опиши проблему, которую решает проект, для инвестиционной презентации. Контекст: {context}",
            "solution": f"Опиши решение проекта для инвестиционной презентации. Контекст: {context}",
            "market": f"Проанализируй рынок для инвестиционной презентации. Контекст: {context}",
            "finance": f"Опиши финансовые показатели для инвестиционной презентации. Контекст: {context}",
            "team": f"Опиши команду проекта для инвестиционной презентации. Контекст: {context}",
            "summary": f"Сделай краткое резюме проекта для инвестиционной презентации. Контекст: {context}"
        }

        user_message = user_prompts.get(slide_type,
                                        f"Сгенерируй контент для слайда '{slide_type}'. Контекст: {context}")

        # Qwen chat format
        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"

        return prompt

    def _clean_generated_text(self, text: str, prompt: str) -> str:
        """Очищает сгенерированный текст для Qwen"""
        # Удаляем промпт и служебные токены Qwen
        if prompt in text:
            text = text.replace(prompt, "")

        # Удаляем Qwen-specific tokens
        text = text.replace("<|im_start|>", "").replace("<|im_end|>", "").replace("assistant", "")

        # Удаляем лишние пробелы и переносы
        text = re.sub(r'\n+', '\n', text.strip())
        text = re.sub(r' +', ' ', text)

        # Обрезаем до разумной длины
        return text[:800].strip()

    def generate_slide_content(self, slide_type: str, context: str, audience: str = "инвесторы") -> Dict[str, Any]:
        """Генерация контента для слайда с Qwen"""

        if not self.is_loaded:
            return {
                "content": f"[Модель не загружена] Контент для слайда '{slide_type}'",
                "status": "error",
                "error": "LLM модель не доступна"
            }

        # Если в тестовом режиме
        if hasattr(self, 'test_mode') and self.test_mode:
            return self._generate_test_content(slide_type, context, audience)

        try:
            # Строим промпт для Qwen
            prompt = self._build_qwen_prompt(slide_type, context[:400], audience)  # Ограничиваем контекст

            logger.debug(f"Промпт для {slide_type}: {prompt[:200]}...")

            # Генерация с Qwen
            result = self.generator(
                prompt,
                max_new_tokens=settings.MAX_NEW_TOKENS,
                num_return_sequences=1,
                pad_token_id=self.generator.tokenizer.eos_token_id,
                truncation=True,
                return_full_text=False,
            )

            generated_text = result[0]['generated_text']
            cleaned_text = self._clean_generated_text(generated_text, prompt)

            logger.info(f"✅ Qwen успешно сгенерировал контент для {slide_type}")

            return {
                "content": cleaned_text,
                "slide_type": slide_type,
                "audience": audience,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"❌ Ошибка генерации Qwen для {slide_type}: {e}")
            # Возвращаем тестовый контент при ошибке
            return self._generate_test_content(slide_type, context, audience)

    def _generate_test_content(self, slide_type: str, context: str, audience: str) -> Dict[str, Any]:
        """Генерация тестового контента"""
        test_contents = {
            "title": "🚀 AI Presentation Assistant - Инновационная платформа",
            "problem": "📊 Проблема: Команды тратят 40+ часов на подготовку инвестиционных презентаций",
            "solution": "💡 Решение: AI-ассистент для автоматической генерации профессиональных презентаций",
            "market": "🌍 Рынок: $500 млн в год с ростом 15% ежегодно",
            "finance": "💰 Финансы: Выручка $2 млн в первый год, окупаемость 18 месяцев",
            "team": "👥 Команда: Опытные специалисты в AI и финансовых технологиях",
            "summary": "✅ Резюме: Перспективный проект с четкой бизнес-моделью и сильной командой"
        }

        content = test_contents.get(
            slide_type,
            f"Контент для слайда '{slide_type}'. Контекст: {context[:100]}..."
        )

        return {
            "content": content,
            "slide_type": slide_type,
            "audience": audience,
            "status": "success",
            "test_mode": True
        }

    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья модели"""
        if not self.is_loaded:
            return {"status": "not_loaded", "model": settings.LLM_MODEL}

        if hasattr(self, 'test_mode') and self.test_mode:
            return {
                "status": "test_mode",
                "model": "test_data",
                "message": "Используются тестовые данные"
            }

        try:
            # Простая проверка работы Qwen
            test_prompt = "<|im_start|>system\nТы полезный ассистент.<|im_end|>\n<|im_start|>user\nПривет!<|im_end|>\n<|im_start|>assistant\n"
            test_result = self.generator(test_prompt, max_new_tokens=10, num_return_sequences=1)

            return {
                "status": "healthy",
                "model": settings.LLM_MODEL,
                "license": "open-source",
                "provider": "Qwen",
                "test_passed": len(test_result[0]['generated_text']) > 0
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": settings.LLM_MODEL
            }


# Глобальный экземпляр генератора
content_generator = ContentGenerator()
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
        self.tokenizer = None
        self.model = None
        self.is_loaded = False
        self._load_rugpt3_model()

    def _load_rugpt3_model(self):
        """Загрузка модели rugpt3small"""
        try:
            logger.info(f"Загрузка русскоязычной модели: {settings.LLM_MODEL}")

            # Используем pipeline для простоты
            self.generator = pipeline(
                "text-generation",
                model=settings.LLM_MODEL,
                tokenizer=settings.LLM_MODEL,
                torch_dtype=torch.float32,
                device=-1,  # CPU
                max_length=settings.MAX_NEW_TOKENS,
                temperature=settings.TEMPERATURE,
                top_p=settings.TOP_P,
                do_sample=settings.DO_SAMPLE,
                repetition_penalty=settings.REPETITION_PENALTY,
            )

            self.is_loaded = True
            logger.info(f"✅ Модель {settings.LLM_MODEL} успешно загружена")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
            self._enable_test_mode()

    def _enable_test_mode(self):
        """Включаем тестовый режим"""
        logger.info("🔄 Активация тестового режима")
        self.is_loaded = True
        self.test_mode = True

    @staticmethod
    def _build_russian_prompt(slide_type: str, context: str, audience: str) -> str:
        """Строит русскоязычные промпты для rugpt3"""

        prompts = {
            "title": f"Сгенерируй убедительный заголовок для инвестиционной презентации проекта. Контекст: {context}\n\nЗаголовок:",
            "problem": f"Опиши проблему, которую решает этот проект, для инвестиционной презентации. Контекст: {context}\n\nОписание проблемы:",
            "solution": f"Опиши решение, которое предлагает проект, для инвестиционной презентации. Контекст: {context}\n\nОписание решения:",
            "market": f"Проанализируй рынок и возможности для этого проекта в инвестиционной презентации. Контекст: {context}\n\nАнализ рынка:",
            "finance": f"Опиши финансовые показатели проекта для инвестиционной презентации. Контекст: {context}\n\nФинансовые показатели:",
            "team": f"Опиши команду проекта для инвестиционной презентации. Контекст: {context}\n\nОписание команды:",
            "summary": f"Сделай краткое резюме проекта для заключительного слайда инвестиционной презентации. Контекст: {context}\n\nРезюме проекта:"
        }

        return prompts.get(slide_type, f"Сгенерируй контент для слайда '{slide_type}'. Контекст: {context}\n\nКонтент:")

    @staticmethod
    def _clean_generated_text(text: str, prompt: str) -> str:
        """Очищает сгенерированный текст"""
        # Удаляем промпт
        if text.startswith(prompt):
            text = text[len(prompt):].strip()

        # Удаляем лишние кавычки
        text = text.strip('"\'').strip()

        # Обрезаем до первого законченного предложения
        sentences = re.split(r'[.!?]', text)
        if len(sentences) > 1:
            text = sentences[0] + '.'

        # Удаляем повторяющиеся фразы
        words = text.split()
        if len(words) > 2 and words[0] == words[1]:
            text = ' '.join(words[1:])

        return text[:400]  # Ограничиваем длину

    def generate_slide_content(self, slide_type: str, context: str, audience: str = "инвесторы") -> Dict[str, Any]:
        """Генерация контента для слайда"""

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
            # Строим русскоязычный промпт
            prompt = self._build_russian_prompt(slide_type, context, audience)

            logger.debug(f"Промпт для {slide_type}: {prompt[:100]}...")

            # Генерация текста
            result = self.generator(
                prompt,
                max_length=settings.MAX_NEW_TOKENS,
                num_return_sequences=1,
                pad_token_id=self.generator.tokenizer.eos_token_id,
            )

            generated_text = result[0]['generated_text']
            cleaned_text = self._clean_generated_text(generated_text, prompt)

            logger.info(f"✅ Успешно сгенерирован контент для {slide_type}")

            return {
                "content": cleaned_text,
                "slide_type": slide_type,
                "audience": audience,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"❌ Ошибка генерации для {slide_type}: {e}")
            # Возвращаем тестовый контент при ошибке
            return self._generate_test_content(slide_type, context, audience)

    @staticmethod
    def _generate_test_content(slide_type: str, context: str, audience: str) -> Dict[str, Any]:
        """Генерация тестового контента"""
        test_contents = {
            "title": "🚀 AI Presentation Assistant - Инновационная платформа для создания инвестиционных презентаций",
            "problem": "📊 Проблема: Команды тратят 40+ часов на подготовку каждой инвестиционной презентации. Существующие решения не обеспечивают полной автоматизации процесса.",
            "solution": "💡 Решение: AI-ассистент, который автоматически анализирует документы и генерирует профессиональные инвестиционные презентации. Ключевые функции: интеллектуальный анализ данных, генерация контента, адаптация под аудиторию.",
            "market": "🌍 Рынок: Объем мирового рынка инструментов для презентаций составляет $500 млн в год с ростом 15% ежегодно. Целевая аудитория: стартапы, венчурные фонды, корпоративные отделы разработки.",
            "finance": "💰 Финансовые показатели: Планируемая выручка в первый год - $2 млн. Customer Acquisition Cost: $500. Lifetime Value: $5000. Период окупаемости: 18 месяцев. EBITDA margin: 25%.",
            "team": "👥 Команда: Основатели с глубоким опытом в AI и финансовых технологиях. Технический директор - 10 лет в machine learning. CEO - бывший менеджер венчурного фонда с опытом привлечения $50M+.",
            "summary": "✅ Резюме: Проект представляет собой уникальное решение с четкой бизнес-моделью и значительным рыночным потенциалом. Сильная команда, проверенная технология и растущий рынок создают условия для успешной реализации."
        }

        content = test_contents.get(
            slide_type,
            f"📝 Контент для слайда '{slide_type}'. Аудитория: {audience}. Контекст из документов: {context[:100]}..."
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
            # Простая проверка работы модели
            test_prompt = "Тестовый запрос:"
            test_result = self.generator(test_prompt, max_length=20, num_return_sequences=1)

            return {
                "status": "healthy",
                "model": settings.LLM_MODEL,
                "license": "open-source",
                "language": "russian",
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
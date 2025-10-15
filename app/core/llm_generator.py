import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from app.config import settings
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self):
        self.generator = None
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        try:
            logger.info(f"Загрузка модели: {settings.LLM_MODEL}")

            self.tokenizer = AutoTokenizer.from_pretrained(
                settings.LLM_MODEL,
                trust_remote_code=True
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                settings.LLM_MODEL,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="auto"
            )

            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                max_new_tokens=150,
                temperature=0.3,
                trust_remote_code=True
            )

            self.is_loaded = True
            logger.info("✅ Модель загружена")

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            raise

    def generate_slide_content(self, slide_type: str, context: str, audience: str = "инвесторы") -> Dict[str, Any]:
        if not self.is_loaded:
            raise Exception("Модель не загружена")

        prompt = self._create_prompt(slide_type, context, audience)
        result = self.generator(prompt)[0]['generated_text']

        # Убираем промпт из результата
        content = result.replace(prompt, "").strip()
        content = self._clean_content(content, slide_type)

        return {
            "content": content,
            "slide_type": slide_type,
            "audience": audience,
            "status": "success"
        }

    def _clean_content(self, text: str, slide_type: str) -> str:
        if slide_type == "title":
            # Берем первую строку, убираем кавычки, ограничиваем 6 словами
            first_line = text.split('\n')[0].strip()
            first_line = first_line.replace('"', '').replace("'", "")
            words = first_line.split()[:6]
            return ' '.join(words)
        else:
            # Берем первые 3-4 пункта с маркерами
            lines = []
            for line in text.split('\n'):
                line = line.strip()
                if line and (line.startswith('•') or line.startswith('-') or len(line) > 20):
                    if len(line) <= 100:  # Ограничиваем длину
                        lines.append(line)
                if len(lines) >= 4:
                    break
            return '\n'.join(lines) if lines else "• Информация готовится\n• Данные анализируются\n• Результаты будут представлены"

    def _create_prompt(self, slide_type: str, context: str, audience: str) -> str:
        # Улучшенные промпты
        prompts = {
            "title": "Создай краткий убедительный заголовок для инвестиционной презентации (4-6 слов). Только заголовок:",
            "problem": """Опиши проблему проекта для слайда презентации. Используй 3-4 пункта:
• Основная проблема рынка
• Существующие ограничения  
• Последствия проблемы
Формат - список с маркерами:""",
            "solution": """Опиши решение проекта для слайда презентации. Используй 3-4 пункта:
• Ключевое решение
• Основные преимущества
• Уникальные особенности
Формат - список с маркерами:""",
            "market": """Проанализируй рынок для слайда презентации. Используй 3-4 пункта:
• Объем и динамика рынка
• Целевая аудитория  
• Тренды и перспективы
Формат - список с маркерами:""",
            "finance": """Представь финансовые показатели для слайда презентации. Используй 3-4 пункта:
• Ключевые метрики
• Прогнозы роста
• Инвестиционная привлекательность
Формат - список с маркерами:""",
            "team": """Опиши команду проекта для слайда презентации. Используй 3-4 пункта:
• Ключевые участники
• Опыт и компетенции
• Успешные проекты
Формат - список с маркерами:""",
            "summary": """Сделай резюме проекта для слайда презентации. Используй 3-4 пункта:
• Основные преимущества
• Ключевые показатели
• Перспективы развития
Формат - список с маркерами:"""
        }

        base_prompt = prompts.get(slide_type, "Создай контент для слайда презентации в формате списка с маркерами:")
        return f"{base_prompt}\n\nКонтекст: {context[:100]}\nАудитория: {audience}"

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.is_loaded else "not_loaded",
            "model": settings.LLM_MODEL
        }


content_generator = ContentGenerator()
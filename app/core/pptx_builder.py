from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import io
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class PresentationBuilder:
    def __init__(self):
        self.prs = Presentation()
        self.slide_width = self.prs.slide_width
        self.slide_height = self.prs.slide_height
        self._setup_default_layout()

    def _setup_default_layout(self):
        """Настраивает базовые стили презентации"""
        # Устанавливаем размер слайдов (16:9)
        self.prs.slide_width = Inches(13.333)
        self.prs.slide_height = Inches(7.5)

    def add_title_slide(self, title: str, subtitle: Optional[str] = None):
        """Добавляет титульный слайд"""
        slide_layout = self.prs.slide_layouts[0]  # Title slide
        slide = self.prs.slides.add_slide(slide_layout)

        # Заголовок
        if slide.shapes.title:
            slide.shapes.title.text = title
            self._format_title(slide.shapes.title)

        # Подзаголовок
        if subtitle and len(slide.placeholders) > 1:
            subtitle_placeholder = slide.placeholders[1]
            subtitle_placeholder.text = subtitle
            self._format_subtitle(subtitle_placeholder)

        return slide

    def add_content_slide(self, title: str, content: str, content_type: str = "text"):
        """Добавляет слайд с заголовком и контентом"""
        slide_layout = self.prs.slide_layouts[1]  # Title and Content
        slide = self.prs.slides.add_slide(slide_layout)

        # Заголовок
        if slide.shapes.title:
            slide.shapes.title.text = title
            self._format_slide_title(slide.shapes.title)

        # Контент
        if len(slide.placeholders) > 1:
            content_placeholder = slide.placeholders[1]
            self._format_content(content_placeholder, content, content_type)

        return slide

    def add_section_slide(self, section_title: str):
        """Добавляет разделительный слайд"""
        slide_layout = self.prs.slide_layouts[1]  # Title and Content
        slide = self.prs.slides.add_slide(slide_layout)

        # Создаем красивый разделитель
        title_shape = slide.shapes.title
        title_shape.text = section_title
        self._format_section_title(title_shape)
        # Добавляем декоративную линию
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(1), Inches(4),
            Inches(11.333), Inches(0.1)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(0, 112, 192)  # Синий цвет

        return slide

    @staticmethod
    def _format_title(shape):
        """Форматирование главного заголовка"""
        for paragraph in shape.text_frame.paragraphs:
            paragraph.font.size = Pt(44)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(0, 0, 0)
            paragraph.alignment = PP_ALIGN.CENTER

    @staticmethod
    def _format_subtitle(shape):
        """Форматирование подзаголовка"""
        for paragraph in shape.text_frame.paragraphs:
            paragraph.font.size = Pt(18)
            paragraph.font.color.rgb = RGBColor(128, 128, 128)
            paragraph.alignment = PP_ALIGN.CENTER

    @staticmethod
    def _format_slide_title(shape):
        """Форматирование заголовка слайда"""
        for paragraph in shape.text_frame.paragraphs:
            paragraph.font.size = Pt(32)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(0, 0, 0)

    @staticmethod
    def _format_section_title(shape):
        """Форматирование заголовка раздела"""
        for paragraph in shape.text_frame.paragraphs:
            paragraph.font.size = Pt(36)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(0, 112, 192)  # Синий
            paragraph.alignment = PP_ALIGN.CENTER

    @staticmethod
    def _format_content(shape, content: str, content_type: str = "text"):
        """Форматирование контента слайда"""
        text_frame = shape.text_frame
        text_frame.clear()  # Очищаем стандартный текст

        if content_type == "bullets":
            # Форматируем как маркированный список
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    p = text_frame.add_paragraph()
                    p.text = line.strip()
                    p.level = 0
                    p.font.size = Pt(18)
                    p.font.color.rgb = RGBColor(0, 0, 0)
                    p.space_after = Pt(6)
        else:
            # Простой текст
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    p = text_frame.add_paragraph()
                    p.text = para.strip()
                    p.font.size = Pt(18)
                    p.font.color.rgb = RGBColor(0, 0, 0)
                    p.space_after = Pt(12)

    def add_slide(self, slide_type: str, title: str, content: str, audience: Optional[str] = None):
        """Универсальный метод добавления слайда (для обратной совместимости)"""
        if slide_type == "title":
            return self.add_title_slide(title, content)
        else:
            return self.add_content_slide(title, content)

    def create_standard_presentation(self, slides_data: List[dict]):
        """Создает презентацию из готовых данных"""
        for i, slide_data in enumerate(slides_data):
            if i == 0:  # Первый слайд - титульный
                self.add_title_slide(
                    slide_data.get("title", "Презентация"),
                    slide_data.get("content", "Сгенерировано AI Assistant")
                )
            else:
                self.add_content_slide(
                    slide_data.get("title", "Слайд"),
                    slide_data.get("content", ""),
                    slide_data.get("content_type", "text")
                )

    def save_to_bytes(self) -> io.BytesIO:
        """Сохраняет презентацию в bytes"""
        try:
            presentation_bytes = io.BytesIO()
            self.prs.save(presentation_bytes)
            presentation_bytes.seek(0)
            logger.info("Презентация успешно сохранена в bytes")
            return presentation_bytes
        except Exception as e:
            logger.error(f"Ошибка сохранения презентации: {e}")
            raise

    def get_slide_count(self) -> int:
        """Возвращает количество слайдов"""
        return len(self.prs.slides)
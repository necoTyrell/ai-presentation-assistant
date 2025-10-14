from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Tuple, Dict, Any
import logging
from sklearn.metrics.pairwise import cosine_similarity
import uuid

logger = logging.getLogger(__name__)

# Загружаем модель для эмбеддингов
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


class DocumentIndex:
    def __init__(self):
        self.documents = []  # Храним документы с метаданными
        self.embeddings = None
        self.is_built = False

    def add_documents(self, documents: List[dict]):
        """Добавляет документы в индекс"""
        for doc in documents:
            # Добавляем основной текст
            if doc.get("text") and doc["text"].strip():
                self.documents.append({
                    "id": str(uuid.uuid4()),
                    "content": doc["text"],
                    "type": "text",
                    "source": doc["metadata"]["filename"],
                    "content_type": "main_text"
                })

            # Добавляем таблицы
            for i, table in enumerate(doc.get("tables", [])):
                if table:
                    table_text = self._table_to_text(table, doc['metadata']['filename'], i)
                    self.documents.append({
                        "id": str(uuid.uuid4()),
                        "content": table_text,
                        "type": "table",
                        "source": doc["metadata"]["filename"],
                        "content_type": "table",
                        "table_index": i
                    })

        logger.info(f"Добавлено {len(documents)} файлов, всего чанков: {len(self.documents)}")

    @staticmethod
    def _table_to_text(table, filename: str, index: int) -> str:
        """Конвертирует таблицу в текстовый формат"""
        table_text = f"Таблица {index + 1} из {filename}:\n"

        for row_idx, row in enumerate(table):
            if isinstance(row, list):
                row_text = " | ".join([str(cell).strip() for cell in row if cell is not None])
            else:
                row_text = str(row).strip()

            if row_text:
                table_text += f"Строка {row_idx}: {row_text}\n"

        return table_text.strip()

    def build_index(self):
        """Строит индекс с помощью эмбеддингов"""
        if not self.documents:
            logger.warning("Нет документов для индексации")
            return

        logger.info("Построение индекса с помощью эмбеддингов...")

        # Создаем эмбеддинги для всех документов
        texts = [doc["content"] for doc in self.documents]
        self.embeddings = model.encode(texts, convert_to_numpy=True)

        self.is_built = True
        logger.info(f"Индекс построен. Документов: {len(self.documents)}, Размерность: {self.embeddings.shape[1]}")

    def search(self, query: str, k: int = 5) -> List[Tuple[str, str, str]]:
        """Поиск релевантных документов с помощью косинусного сходства"""
        if not self.is_built or not self.documents:
            logger.warning("Индекс не построен или нет документов")
            return []

        try:
            # Создаем эмбеддинг для запроса
            query_embedding = model.encode([query], convert_to_numpy=True)

            # Вычисляем косинусное сходство
            similarities = cosine_similarity(query_embedding, self.embeddings)[0]

            # Получаем топ-K наиболее похожих документов
            top_indices = np.argsort(similarities)[-k:][::-1]

            results = []
            for idx in top_indices:
                if idx < len(self.documents):
                    doc = self.documents[idx]
                    results.append((
                        doc["content"],  # content
                        doc["type"],  # content_type
                        doc["source"]  # source filename
                    ))

            logger.debug(f"Найдено {len(results)} результатов для запроса: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику индекса"""
        return {
            "documents_count": len(self.documents),
            "index_built": self.is_built,
            "embedding_dim": self.embeddings.shape[1] if self.embeddings is not None else 0,
            "backend": "sentence-transformers + cosine_similarity"
        }

    def clear(self):
        """Очищает индекс"""
        self.documents = []
        self.embeddings = None
        self.is_built = False
        logger.info("Индекс очищен")


# Глобальный экземпляр индекса документов
document_index = DocumentIndex()
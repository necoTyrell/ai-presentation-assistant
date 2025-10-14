from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from typing import List, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Загружаем предобученную модель
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


class DocumentIndex:
    def __init__(self):
        self.texts: List[Dict[str, Any]] = []  # Храним тексты с метаданными
        self.embeddings: np.ndarray = None
        self.index = None
        self.is_built: bool = False

    def add_documents(self, documents: List[dict]):
        """Добавляет документы в индекс"""
        for doc in documents:
            # Добавляем основной текст
            if doc.get("text"):
                self.texts.append({
                    "content": doc["text"],
                    "type": "text",
                    "source": doc["metadata"]["filename"],
                    "characters": len(doc["text"])
                })

            # Добавляем таблицы как отдельные чанки
            for i, table in enumerate(doc.get("tables", [])):
                table_text = f"Таблица {i + 1} из {doc['metadata']['filename']}:\n"
                # Конвертируем таблицу в текстовый формат
                for row_idx, row in enumerate(table):
                    if isinstance(row, list):
                        row_text = "\t".join([str(cell) for cell in row])
                    else:
                        row_text = str(row)
                    table_text += f"Строка {row_idx}: {row_text}\n"

                self.texts.append({
                    "content": table_text,
                    "type": "table",
                    "source": doc["metadata"]["filename"],
                    "table_index": i
                })

        logger.info(f"Добавлено {len(documents)} документов, всего чанков: {len(self.texts)}")

    def build_index(self):
        """Строит FAISS индекс"""
        if not self.texts:
            logger.warning("Нет документов для индексации")
            return

        logger.info("Начинаем построение индекса...")

        # Извлекаем только содержимое для эмбеддингов
        texts_content = [item["content"] for item in self.texts]

        # Создаем эмбеддинги
        self.embeddings = model.encode(texts_content, convert_to_numpy=True, show_progress_bar=True)

        # Строим индекс
        dim = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(self.embeddings)
        self.is_built = True

        logger.info(f"Индекс построен. Размерность: {dim}, векторов: {len(self.embeddings)}")

    def search(self, query: str, k: int = 5) -> List[Tuple[str, str]]:
        """Поиск релевантных документов"""
        if not self.index or not self.is_built:
            logger.error("Индекс не построен. Сначала вызовите build_index()")
            return []

        if not self.texts:
            logger.warning("Нет документов для поиска")
            return []

        try:
            # Создаем эмбеддинг для запроса
            query_emb = model.encode([query], convert_to_numpy=True)

            # Ищем k ближайших соседей
            distances, indices = self.index.search(query_emb, min(k, len(self.texts)))

            results = []
            for i in indices[0]:
                if i < len(self.texts):
                    doc = self.texts[i]
                    results.append((doc["content"], doc["type"], doc["source"]))

            logger.debug(f"Поиск '{query}' вернул {len(results)} результатов")
            return results

        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику индекса"""
        return {
            "documents_count": len(self.texts),
            "index_built": self.is_built,
            "index_size": self.embeddings.shape[0] if self.embeddings is not None else 0,
            "embedding_dim": self.embeddings.shape[1] if self.embeddings is not None else 0,
            "sources": list(set(doc["source"] for doc in self.texts)) if self.texts else []
        }

    def clear(self):
        """Очищает индекс"""
        self.texts = []
        self.embeddings = None
        self.index = None
        self.is_built = False
        logger.info("Индекс очищен")


# Глобальный экземпляр индекса документов
document_index = DocumentIndex()


# Сохраняем старые функции для обратной совместимости
def create_embeddings(texts: List[str]):
    """Создает эмбеддинги для списка текстов"""
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


def build_faiss_index(embeddings: np.ndarray):
    """Создает FAISS-индекс для поиска по векторным представлениям"""
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index


def search_similar(query: str, texts: List[str], index, k: int = 3):
    """Возвращает K наиболее релевантных текстов к запросу"""
    query_emb = model.encode([query], convert_to_numpy=True)
    distances, indices = index.search(query_emb, k)
    results = [texts[i] for i in indices[0]]
    return results
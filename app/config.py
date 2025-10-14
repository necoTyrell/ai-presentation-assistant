from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Модели HuggingFace
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    LLM_MODEL: str = "IlyaGusev/fred_t5_ru_turbo"  # Хорошая русскоязычная модель
    # Альтернативы: "mistralai/Mistral-7B-Instruct-v0.1" (требует больше ресурсов)

    # Настройки генерации
    MAX_NEW_TOKENS: int = 512
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.9
    DO_SAMPLE: bool = True

    # Настройки оборудования
    DEVICE: str = "cuda"  # или "cpu"
    LOAD_IN_8BIT: bool = True  # для экономии памяти

    class Config:
        env_file = ".env"


settings = Settings()
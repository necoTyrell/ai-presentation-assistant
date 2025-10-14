from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Эмбеддинги
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # QWEN модель - выбираем подходящую версию
    LLM_MODEL: str = "Qwen/Qwen2.5-0.5B-Instruct"  # ← МЕНЯЕМ НА QWEN
    # Альтернативы:
    # "Qwen/Qwen2.5-1.5B-Instruct" - чуть мощнее
    # "Qwen/Qwen2.5-0.5B" - базовая

    # Настройки генерации для Qwen
    MAX_NEW_TOKENS: int = 500  # ← УВЕЛИЧИВАЕМ для Qwen
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.9
    DO_SAMPLE: bool = True

    # Настройки оборудования
    DEVICE: str = "cpu"  # Qwen хорошо работает на CPU
    LOAD_IN_8BIT: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
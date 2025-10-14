from fastapi import FastAPI
from app.api import upload, generate
from app.core.embeddings import document_index
from app.core.llm_generator import content_generator

app = FastAPI(title="AI Presentation Assistant")

app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(generate.router, prefix="/generate", tags=["generate"])
app.include_router(llm.router, prefix="/llm", tags=["llm"])


@app.get("/")
def root():
    return {
        "message": "AI Presentation Assistant is running 🚀",
        "endpoints": {
            "upload": "/upload",
            "generate": "/generate/presentation",
            "llm_test": "/llm/test-generate",
            "llm_status": "/llm/model-status"
        }
    }


@app.get("/health")
def health_check():
    """Проверка здоровья всех компонентов системы"""
    model_health = content_generator.health_check()
    documents_loaded = len(document_index.texts) > 0

    return {
        "status": "healthy" if model_health["status"] in ["healthy", "loaded"] else "degraded",
        "components": {
            "llm_model": model_health,
            "document_index": {
                "loaded": documents_loaded,
                "documents_count": len(document_index.texts),
                "index_built": document_index.index is not None
            }
        }
    }

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from src.services.storage import chroma_service
from src.services.ingestion import document_processor
from src.utils.logger import stage_logger, ProcessingStage
from config import settings

router = APIRouter()

@router.delete("/reset", 
              summary="Reset database and files",
              description="WARNING: This will delete all documents from ChromaDB and all uploaded files")
async def reset_database():
    """
    Reset the entire application data including ChromaDB and uploaded files.
    WARNING: This operation is irreversible and will delete all data.
    """
    try:
        result = document_processor.reset_application_data()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Database and files have been reset successfully",
                "data": result
            }
        )
    except Exception as e:
        stage_logger.error(ProcessingStage.FAILED, f"Database reset failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database reset failed: {str(e)}"
        )


@router.get("/embedding-info",
           summary="Get embedding model information", 
           description="Get current embedding model configuration and status")
async def get_embedding_info():
    """
    Get information about the current embedding model configuration.
    """
    try:
        embedding_info = {
            "current_model": "OpenAI" if settings.USE_OPENAI_EMBEDDINGS else "Local HuggingFace",
            "openai_model": settings.OPENAI_EMBEDDING_MODEL if settings.USE_OPENAI_EMBEDDINGS else None,
            "local_model": settings.LOCAL_EMBEDDING_MODEL if not settings.USE_OPENAI_EMBEDDINGS else None,
            "openai_api_key_configured": bool(settings.OPENAI_API_KEY),
            "use_openai_embeddings": settings.USE_OPENAI_EMBEDDINGS,
            "embedding_dimensions": {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072, 
                "text-embedding-ada-002": 1536,
                "BAAI/bge-base-en-v1.5": 768
            },
            "cost_per_1k_tokens": {
                "text-embedding-3-small": "$0.00002",
                "text-embedding-3-large": "$0.00013",
                "text-embedding-ada-002": "$0.0001"
            },
            "recommendation": "text-embedding-3-small is recommended for best cost/performance ratio"
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "data": embedding_info
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving embedding info: {str(e)}"
        )


@router.get("/collection-info",
           summary="Get ChromaDB collection information",
           description="Get information about the current ChromaDB collection and embedding dimensions")
async def get_collection_info():
    """
    Get information about the current ChromaDB collection.
    """
    try:
        collection_info = chroma_service.get_collection_info()
        
        # Add embedding model info
        collection_info.update({
            "current_embedding_model": "OpenAI" if settings.USE_OPENAI_EMBEDDINGS else "Local HuggingFace",
            "expected_dimensions": {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536,
                "BAAI/bge-base-en-v1.5": 768
            },
            "current_model_dimensions": 1536 if settings.USE_OPENAI_EMBEDDINGS else 768,
            "openai_model": settings.OPENAI_EMBEDDING_MODEL if settings.USE_OPENAI_EMBEDDINGS else None,
            "local_model": settings.LOCAL_EMBEDDING_MODEL if not settings.USE_OPENAI_EMBEDDINGS else None
        })
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "data": collection_info
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving collection info: {str(e)}"
        )


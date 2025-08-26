from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from src.services.storage import chroma_service
from src.services.ingestion import document_processor
from src.utils.logger import stage_logger, ProcessingStage

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




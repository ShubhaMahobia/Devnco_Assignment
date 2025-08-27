from fastapi import APIRouter
from datetime import datetime
import os
from config import settings

router = APIRouter()

@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.API_VERSION,
        "upload_dir_exists": os.path.exists(settings.UPLOAD_DIR)
    }


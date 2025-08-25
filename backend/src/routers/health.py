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

@router.get("/detailed")
async def detailed_health_check():
    """Detailed health check with system information"""
    upload_dir_info = {}
    if os.path.exists(settings.UPLOAD_DIR):
        try:
            files_count = len([f for f in os.listdir(settings.UPLOAD_DIR) 
                             if os.path.isfile(os.path.join(settings.UPLOAD_DIR, f))])
            upload_dir_info = {
                "exists": True,
                "files_count": files_count,
                "path": settings.UPLOAD_DIR
            }
        except Exception as e:
            upload_dir_info = {
                "exists": True,
                "error": str(e),
                "path": settings.UPLOAD_DIR
            }
    else:
        upload_dir_info = {
            "exists": False,
            "path": settings.UPLOAD_DIR
        }
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.API_VERSION,
        "config": {
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "allowed_file_types": settings.ALLOWED_FILE_TYPES,
            "debug": settings.DEBUG
        },
        "storage": upload_dir_info
    }

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def auth_status():
    """Placeholder for authentication endpoints"""
    return {
        "message": "Authentication endpoints - Coming soon",
        "status": "placeholder"
    }

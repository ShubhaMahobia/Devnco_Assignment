from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from src.routers import files, health, auth, qa, database
from config import settings
from src.utils.logger import StageLogger, ProcessingStage

# Initialize logger
logger = StageLogger("main")

# Create FastAPI app instance
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    debug=settings.DEBUG
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(files.router, prefix="/api/v1/files", tags=["File Management"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(qa.router, prefix="/api/v1/qa", tags=["Question & Answer"])
app.include_router(database.router, prefix="/api/v1/database", tags=["Database Management"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(ProcessingStage.FAILED, f"Unhandled exception: {str(exc)} | Path: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to RAG Application API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }

def main():
    """Run the FastAPI application"""
    logger.info(
        ProcessingStage.UPLOADING,
        f"Starting FastAPI server - Host: {settings.HOST}, Port: {settings.PORT}, Debug: {settings.DEBUG}, Version: {settings.API_VERSION}"
    )
    
    try:
        uvicorn.run(
            "src.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG
        )
    except KeyboardInterrupt:
        logger.info(ProcessingStage.UPLOADING, "Server stopped by user")
    except Exception as e:
        logger.error(ProcessingStage.FAILED, f"Server startup failed: {str(e)}")

if __name__ == "__main__":
    main()
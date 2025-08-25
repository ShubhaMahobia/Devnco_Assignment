import os
from typing import List

class Settings:
    # File upload settings
    MAX_FILE_SIZE_MB: int = 50  # Configurable max file size in MB
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".docx", ".txt"]
    UPLOAD_DIR: str = "storage/uploads"
    
    # Document processing settings
    CHUNK_SIZE: int = 800  # Default chunk size for text splitting
    CHUNK_OVERLAP: int = 175  # Default overlap between chunks (150-200 range)
    
    # API settings
    API_TITLE: str = "RAG Application API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Backend API for RAG (Retrieval-Augmented Generation) application"
    
    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    def __init__(self):
        # Ensure upload directory exists
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

# Create global settings instance
settings = Settings()

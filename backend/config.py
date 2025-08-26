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
    
    # Embedding settings
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"  # BGE embedding model
    EMBEDDING_DEVICE: str = "cpu"  # Use "cuda" if GPU is available
    NORMALIZE_EMBEDDINGS: bool = True  # Normalize embeddings for better similarity
    
    # ChromaDB settings
    CHROMA_DB_PATH: str = "storage/chromadb"  # ChromaDB persistent storage path
    CHROMA_COLLECTION_NAME: str = "documents"  # Collection name for documents
    
    # API settings
    API_TITLE: str = "RAG Application API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Backend API for RAG (Retrieval-Augmented Generation) application"
    
    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    def __init__(self):
        # Ensure directories exist
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.CHROMA_DB_PATH, exist_ok=True)

# Create global settings instance
settings = Settings()

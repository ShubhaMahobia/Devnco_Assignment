import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # File upload settings
    MAX_FILE_SIZE_MB: int = 50  # Configurable max file size in MB
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".docx", ".txt"]
    UPLOAD_DIR: str = "storage/uploads"  # Local fallback directory
    
    # S3 storage settings
    USE_S3_STORAGE: bool = True  # Enable S3 storage
    S3_BUCKET_NAME: str = "my-rag-bucket-assignment"
    S3_BUCKET_FOLDER: str = "storage"  # Folder within the bucket
    S3_REGION: str = "ap-south-1"
    S3_BASE_URL: str = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{S3_BUCKET_FOLDER}/"
    
    # AWS credentials (optional - can use IAM roles or AWS CLI config)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    
    # Document processing settings
    CHUNK_SIZE: int = 800  # Default chunk size for text splitting
    CHUNK_OVERLAP: int = 175  # Default overlap between chunks (150-200 range)
    
    # OpenAI Embedding settings
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"  # OpenAI embedding model
    # Available OpenAI models:
    # - text-embedding-3-small: 1536 dimensions, $0.00002/1K tokens (recommended)
    # - text-embedding-3-large: 3072 dimensions, $0.00013/1K tokens (higher quality)
    # - text-embedding-ada-002: 1536 dimensions, $0.0001/1K tokens (legacy)
    
    # ChromaDB settings
    CHROMA_DB_PATH: str = "storage/chromadb"  # ChromaDB persistent storage path
    CHROMA_COLLECTION_NAME: str = "documents"  # Collection name for documents
    
    # LLM settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # OpenAI API key from environment
    LLM_MODEL: str = "gpt-4o"  # Default LLM model
    LLM_TEMPERATURE: float = 0.1  # Temperature for response generation
    LLM_MAX_TOKENS: int = 2000  # Maximum tokens for response
    
    # RAG settings
    DEFAULT_RETRIEVAL_K: int = 5  # Default number of documents to retrieve
    MAX_RETRIEVAL_K: int = 20  # Maximum number of documents to retrieve
    MIN_SIMILARITY_THRESHOLD: float = 0.5  # Minimum similarity threshold for retrieval
    
    # API settings
    API_TITLE: str = "RAG Application API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Backend API for RAG (Retrieval-Augmented Generation) application"
    
    # Server settings
    HOST: str = os.getenv("HOST", "127.0.0.1")  # Use 0.0.0.0 for Docker
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    def __init__(self):
        # Ensure directories exist
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.CHROMA_DB_PATH, exist_ok=True)
        
        # Validate OpenAI API key
        if not self.OPENAI_API_KEY:
            print("WARNING: OPENAI_API_KEY not found in environment variables.")
            print("Please set OPENAI_API_KEY to use the Q&A functionality.")

# Create global settings instance
settings = Settings()

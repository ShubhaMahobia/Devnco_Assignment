# RAG Application Backend

A FastAPI-based backend for a Retrieval-Augmented Generation (RAG) application that handles document upload, processing, and question-answering.

## Features

### Current Implementation
- ✅ **File Upload API**: Secure file upload with validation
- ✅ **File Type Support**: PDF, DOCX, TXT files
- ✅ **File Size Limits**: Configurable (default: 50MB)
- ✅ **File Management**: Upload, list, and delete files
- ✅ **Background Processing**: Async file processing pipeline
- ✅ **Health Monitoring**: Health check endpoints
- ✅ **API Documentation**: Auto-generated Swagger/OpenAPI docs

### Planned Features
- 🔄 **Document Processing**: Text extraction from PDF/DOCX
- 🔄 **Vector Storage**: Document embedding and vector database
- 🔄 **Question-Answering**: RAG-based Q&A system
- 🔄 **Authentication**: User management and API security

## Quick Start

### Prerequisites
- Python 3.8+
- pip or uv package manager

### Installation

1. **Clone and navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or using uv:
   ```bash
   uv sync
   ```

3. **Start the server**
   ```bash
   python start_server.py
   ```
   
   Or directly:
   ```bash
   python -m src.main
   ```

4. **Access the application**
   - API Documentation: http://127.0.0.1:8000/docs
   - Health Check: http://127.0.0.1:8000/api/v1/health/
   - Upload Files: http://127.0.0.1:8000/api/v1/files/upload

## API Endpoints

### Health Check
- `GET /api/v1/health/` - Basic health status
- `GET /api/v1/health/detailed` - Detailed system information

### File Management
- `POST /api/v1/files/upload` - Upload a file
- `GET /api/v1/files/list` - List all uploaded files
- `DELETE /api/v1/files/delete/{file_id}` - Delete a specific file

### Authentication (Placeholder)
- `GET /api/v1/auth/` - Authentication endpoints (coming soon)

### Q&A (Placeholder)  
- `GET /api/v1/qa/` - Question & Answer endpoints (coming soon)

## Configuration

Edit `config.py` to customize:

```python
class Settings:
    MAX_FILE_SIZE_MB: int = 50        # Maximum file size
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".docx", ".txt"]
    UPLOAD_DIR: str = "storage/uploads"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
```

## File Upload Specifications

### Supported File Types
- **PDF**: `.pdf` files
- **Word Documents**: `.docx` files  
- **Text Files**: `.txt` files

### File Size Limits
- Default: 50MB maximum
- Configurable via `MAX_FILE_SIZE_MB` setting
- Returns `413 Request Entity Too Large` if exceeded

### Upload Process
1. File validation (type, size, content)
2. Secure filename generation with UUID prefix
3. Local storage in `storage/uploads/` directory
4. Background processing queue (placeholder)
5. Response with file metadata

### Example Upload Response
```json
{
  "filename": "document.pdf",
  "file_id": "uuid-string",
  "file_size": 1024000,
  "file_type": "pdf", 
  "status": "uploaded",
  "upload_timestamp": "2024-01-01T12:00:00",
  "message": "File uploaded successfully and queued for processing"
}
```

## Testing

### Manual Testing with curl
```bash
# Upload a file
curl -X POST "http://127.0.0.1:8000/api/v1/files/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@test_document.txt"

# List files
curl -X GET "http://127.0.0.1:8000/api/v1/files/list"

# Health check
curl -X GET "http://127.0.0.1:8000/api/v1/health/"
```

### Automated Testing
```bash
python test_upload.py
```

## Project Structure

```
backend/
├── config.py                 # Application configuration
├── start_server.py           # Server startup script
├── test_upload.py            # Upload functionality tests
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project metadata
├── src/
│   ├── main.py              # FastAPI application
│   ├── routers/             # API route handlers
│   │   ├── files.py         # File upload/management
│   │   ├── health.py        # Health check endpoints
│   │   ├── auth.py          # Authentication (placeholder)
│   │   └── qa.py            # Q&A endpoints (placeholder)
│   ├── schemas/             # Pydantic models
│   │   ├── file_upload.py   # File upload schemas
│   │   ├── authentication.py
│   │   └── question_and_answer.py
│   ├── services/            # Business logic
│   │   ├── ingestion.py     # File processing pipeline
│   │   ├── retriever.py     # Document retrieval
│   │   └── storage.py       # Data storage
│   └── utils/
│       └── logger.py        # Logging utilities
└── storage/
    └── uploads/             # Uploaded files storage
```

## Development

### Adding New File Types
1. Update `ALLOWED_FILE_TYPES` in `config.py`
2. Add extraction logic in `services/ingestion.py`
3. Update file type enum in `schemas/file_upload.py`

### Extending the Processing Pipeline
The `process_file()` function in `services/ingestion.py` is where document processing logic should be implemented:

```python
async def process_file(file_path: str, file_id: str) -> bool:
    # 1. Extract text from document
    # 2. Split into chunks
    # 3. Generate embeddings  
    # 4. Store in vector database
    # 5. Update file status
    pass
```

## Error Handling

The API returns appropriate HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid file type, empty file)
- `413` - Request Entity Too Large (file size exceeded)
- `422` - Unprocessable Entity (validation errors)
- `500` - Internal Server Error

## Security Considerations

- File names are sanitized and prefixed with UUIDs
- File type validation based on extensions
- File size limits to prevent abuse
- Upload directory is configurable and isolated
- CORS middleware configured (update for production)

## Next Steps

1. **Document Processing**: Implement text extraction for PDF/DOCX
2. **Vector Database**: Add ChromaDB or similar for embeddings
3. **RAG Pipeline**: Implement question-answering with LangChain
4. **Authentication**: Add user management and API keys
5. **Frontend**: Build React/Vue.js interface
6. **Deployment**: Docker containerization and cloud deployment

## Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Ensure all linting passes

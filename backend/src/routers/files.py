import os
import uuid
import shutil
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

from config import settings
from src.schemas.file_upload import FileUploadResponse, FileInfo, UploadError
from src.services.storage import file_storage_service
from src.services.ingestion import document_processor
from src.utils.logger import stage_logger, ProcessingStage

# For now, we'll create a simple logger since the enhanced one might not be implemented yet
import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure storage directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

def get_file_extension(filename: str) -> str:
    """Extract file extension from filename"""
    return Path(filename).suffix.lower()

def is_allowed_file_type(filename: str) -> bool:
    """Check if file type is allowed"""
    extension = get_file_extension(filename)
    return extension in settings.ALLOWED_FILE_TYPES

def generate_unique_filename(original_filename: str) -> tuple[str, str]:
    """Generate unique filename and file ID"""
    file_id = str(uuid.uuid4())
    extension = get_file_extension(original_filename)
    unique_filename = f"{file_id}{extension}"
    return file_id, unique_filename

@router.post("/upload", 
             response_model=FileUploadResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Upload a file",
             description="Upload a text, PDF, or DOCX file to the server")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file (text, PDF, or DOCX) to the server.
    
    - **file**: The file to upload (supported formats: .txt, .pdf, .docx)
    - Returns file information including unique file ID and storage path
    """
    
    # Validate file is provided
    if not file:
        logger.error("No file provided in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Validate filename
    if not file.filename:
        logger.error("No filename provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    try:
        logger.info(f"Starting file upload validation for: {file.filename}")
        
        # Check file type
        if not is_allowed_file_type(file.filename):
            allowed_types = ", ".join(settings.ALLOWED_FILE_TYPES)
            error_msg = f"File type not allowed. Supported types: {allowed_types}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Read file content to check size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Check file size
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            error_msg = f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            logger.error(f"{error_msg}. Received: {file_size / (1024*1024):.2f}MB")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_msg
            )
        
        # Validate file is not empty
        if file_size == 0:
            logger.error("Empty file provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        logger.info(f"File validation passed for: {file.filename} ({file_size} bytes)")
        
        # Generate unique filename and file ID
        file_id, unique_filename = generate_unique_filename(file.filename)
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Save file to storage
        logger.info(f"Saving file to: {file_path}")
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        logger.info(f"Successfully saved file: {file.filename} -> {unique_filename}")
        
        # Create response
        response = FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            status="uploaded"
        )
        
        logger.info(f"File upload completed: {file.filename} ({file_size} bytes)")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error during upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during file upload: {str(e)}"
        )

@router.get("/list", 
            response_model=List[FileInfo],
            summary="List uploaded files",
            description="Get a list of all uploaded files")
async def list_files():
    """
    Get a list of all uploaded files in the storage directory.
    """
    try:
        files_info = []
        
        if not os.path.exists(settings.UPLOAD_DIR):
            logger.info("Upload directory does not exist")
            return files_info
        
        for filename in os.listdir(settings.UPLOAD_DIR):
            file_path = os.path.join(settings.UPLOAD_DIR, filename)
            
            if os.path.isfile(file_path):
                # Extract file info
                file_stats = os.stat(file_path)
                file_size = file_stats.st_size
                upload_timestamp = datetime.fromtimestamp(file_stats.st_ctime)
                
                # Extract file ID from filename (assuming UUID format)
                file_id = Path(filename).stem
                
                # Get original extension for content type
                extension = get_file_extension(filename)
                content_type_map = {
                    '.txt': 'text/plain',
                    '.pdf': 'application/pdf',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                }
                content_type = content_type_map.get(extension, 'application/octet-stream')
                
                file_info = FileInfo(
                    file_id=file_id,
                    filename=filename,
                    file_size=file_size,
                    content_type=content_type,
                    upload_timestamp=upload_timestamp,
                    file_path=file_path
                )
                files_info.append(file_info)
        
        logger.info(f"Listed {len(files_info)} files")
        return files_info
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving file list: {str(e)}"
        )


@router.get("/{file_id}/info",
            response_model=FileInfo,
            summary="Get file information",
            description="Get detailed information about an uploaded file")
async def get_file_info(file_id: str):
    """
    Get detailed information about an uploaded file.
    
    - **file_id**: The unique identifier of the file
    """
    try:
        if not os.path.exists(settings.UPLOAD_DIR):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                file_path = os.path.join(settings.UPLOAD_DIR, filename)
                if os.path.isfile(file_path):
                    # Get file stats
                    file_stats = os.stat(file_path)
                    file_size = file_stats.st_size
                    upload_timestamp = datetime.fromtimestamp(file_stats.st_ctime)
                    
                    # Get content type
                    extension = get_file_extension(filename)
                    content_type_map = {
                        '.txt': 'text/plain',
                        '.pdf': 'application/pdf',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    }
                    content_type = content_type_map.get(extension, 'application/octet-stream')
                    
                    file_info = FileInfo(
                        file_id=file_id,
                        filename=filename,
                        file_size=file_size,
                        content_type=content_type,
                        upload_timestamp=upload_timestamp,
                        file_path=file_path
                    )
                    
                    logger.info(f"Retrieved info for file: {file_id}")
                    return file_info
        
        logger.error(f"File not found: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving file information: {str(e)}"
        )

@router.post("/process", 
             response_model=Dict[str, Any],
             status_code=status.HTTP_201_CREATED)
async def process_document(file: UploadFile = File(...)):

    # Validate file is provided
    if not file or not file.filename:
        stage_logger.error(ProcessingStage.FAILED, "No file provided in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    try:
        result = await document_processor.process_document(file)
        return result
        
    except ValueError as e:
        # Validation errors
        stage_logger.error(ProcessingStage.FAILED, f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected errors
        stage_logger.error(ProcessingStage.FAILED, f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during document processing: {str(e)}"
        )

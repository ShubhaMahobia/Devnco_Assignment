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
from src.services.ingestion import document_processor
from src.utils.logger import ProcessingStage, stage_logger

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
             summary="Upload and process a file",
             description="Upload a text, PDF, or DOCX file to the server and start processing pipeline")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file (text, PDF, or DOCX) to the server and automatically start processing.
    
    - **file**: The file to upload (supported formats: .txt, .pdf, .docx)
    - Returns file information and processing status
    """
    
    
    # Validate filename
    if not file.filename:
        stage_logger.error(ProcessingStage.UPLOADING, "No filename provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    try:
        stage_logger.info(ProcessingStage.UPLOADING, f"Starting file upload validation for: {file.filename}")
        
        # Check file type
        if not is_allowed_file_type(file.filename):
            allowed_types = ", ".join(settings.ALLOWED_FILE_TYPES)
            error_msg = f"File type not allowed. Supported types: {allowed_types}"
            stage_logger.error(ProcessingStage.UPLOADING, error_msg)
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
            stage_logger.error(ProcessingStage.UPLOADING, f"{error_msg}. Received: {file_size / (1024*1024):.2f}MB")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_msg
            )
        
        # Validate file is not empty
        if file_size == 0:
            stage_logger.error(ProcessingStage.UPLOADING, "Empty file provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        stage_logger.info(ProcessingStage.UPLOADING, f"File validation passed for: {file.filename} ({file_size} bytes)")
        
        # Reset file pointer for processing
        await file.seek(0)
        
        # Start the complete processing pipeline
        stage_logger.info(ProcessingStage.UPLOADING, f"Starting document processing pipeline for: {file.filename}")
        
        try:
            # Process the document through the complete pipeline
            processing_result = await document_processor.process_document(file)
            
            # Create enhanced response with processing information
            response = FileUploadResponse(
                file_id=processing_result["file_info"]["file_id"],
                filename=file.filename,
                file_path=processing_result["file_info"]["file_path"],
                file_size=file_size,
                content_type=processing_result["file_info"]["content_type"],
                status="processed"  # Changed from "uploaded" to "processed"
            )
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"File upload and processing completed successfully: {file.filename} "
                            f"({processing_result['processing_stats']['chunks_count']} chunks indexed)")
            
            return response
            
        except Exception as processing_error:
            # If processing fails, still return upload success but with failed status
            stage_logger.error(ProcessingStage.FAILED, 
                             f"Document processing failed for {file.filename}: {str(processing_error)}")
            
            # For now, we'll raise the error. You could alternatively save the file 
            # and return a "uploaded_but_processing_failed" status
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File uploaded but processing failed: {str(processing_error)}"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        stage_logger.error(ProcessingStage.FAILED, f"Unexpected error during upload: {str(e)}")
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

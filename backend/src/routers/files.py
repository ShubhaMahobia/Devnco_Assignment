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

# This function has been removed - using DocumentProcessor.process_document instead

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
            # Process the document through the complete pipeline using DocumentProcessor
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
            # If processing fails, raise the error
            stage_logger.error(ProcessingStage.FAILED, 
                             f"Document processing failed for {file.filename}: {str(processing_error)}")
            
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
    Get a list of all uploaded files using metadata system.
    """
    try:
        files_info = []
        
        if not os.path.exists(settings.UPLOAD_DIR):
            logger.info("Upload directory does not exist")
            return files_info
        
        # Get all file metadata
        from src.services.storage import file_storage_service
        all_metadata = file_storage_service.get_all_files_metadata()
        
        for file_id, metadata in all_metadata.items():
            unique_filename = metadata["unique_filename"]
            storage_type = metadata.get("storage_type", "local")
            
            # Check if file still exists based on storage type
            file_exists = False
            file_path = None
            
            if storage_type == "s3":
                # For S3 files, use the file URL from metadata
                file_path = metadata.get("file_url", "")
                file_exists = True  # Assume S3 files exist (we could add a check if needed)
            else:
                # For local files, check if file exists on disk
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                file_exists = os.path.isfile(file_path)
            
            if file_exists:
                file_info = FileInfo(
                    file_id=file_id,
                    filename=metadata["original_filename"],  # Use original filename
                    file_size=metadata["file_size"],
                    content_type=metadata["content_type"],
                    upload_timestamp=datetime.fromisoformat(metadata["upload_timestamp"]),
                    file_path=file_path
                )
                files_info.append(file_info)
            else:
                # File is missing, clean up metadata
                logger.warning(f"File {unique_filename} missing from storage, cleaning up metadata")
                file_storage_service.delete_file_metadata(file_id)
        
        # Sort by upload timestamp (newest first)
        files_info.sort(key=lambda x: x.upload_timestamp, reverse=True)
        
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
    Get detailed information about an uploaded file using metadata system.
    
    - **file_id**: The unique identifier of the file
    """
    try:
        from src.services.storage import file_storage_service
        
        # Get file metadata
        metadata = file_storage_service.get_file_metadata(file_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        unique_filename = metadata["unique_filename"]
        storage_type = metadata.get("storage_type", "local")
        
        # Check if file exists based on storage type
        file_exists = False
        file_path = None
        
        if storage_type == "s3":
            # For S3 files, use the file URL from metadata
            file_path = metadata.get("file_url", "")
            file_exists = True  # Assume S3 files exist (we could add a check if needed)
        else:
            # For local files, check if file exists on disk
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            file_exists = os.path.isfile(file_path)
        
        if not file_exists:
            # Clean up orphaned metadata
            file_storage_service.delete_file_metadata(file_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        file_info = FileInfo(
            file_id=file_id,
            filename=metadata["original_filename"],  # Use original filename
            file_size=metadata["file_size"],
            content_type=metadata["content_type"],
            upload_timestamp=datetime.fromisoformat(metadata["upload_timestamp"]),
            file_path=file_path
        )
        
        logger.info(f"Retrieved info for file: {file_id}")
        return file_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving file information: {str(e)}"
        )


@router.get("/{file_id}/download",
            summary="Download a file",
            description="Download a file by its ID for viewing or saving")
async def download_file(file_id: str):
    """
    Download a file by its unique ID. For S3 files, creates a temporary download.
    
    - **file_id**: The unique identifier of the file
    """
    try:
        from src.services.storage import file_storage_service
        
        # Get file metadata
        metadata = file_storage_service.get_file_metadata(file_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        storage_type = metadata.get("storage_type", "local")
        unique_filename = metadata["unique_filename"]
        
        if storage_type == "s3":
            # For S3 files, download temporarily for serving
            temp_path = file_storage_service.get_file_path_for_processing(file_id)
            logger.info(f"Serving S3 file for download: {file_id} ({metadata['original_filename']})")
            
            # Return file response with cleanup
            from fastapi.responses import FileResponse
            
            class CleanupFileResponse(FileResponse):
                """Custom FileResponse that cleans up temporary files after serving"""
                def __init__(self, path: str, cleanup_path: str = None, **kwargs):
                    super().__init__(path, **kwargs)
                    self.cleanup_path = cleanup_path
                
                async def __call__(self, scope, receive, send):
                    try:
                        await super().__call__(scope, receive, send)
                    finally:
                        # Clean up temporary file after serving
                        if self.cleanup_path and os.path.exists(self.cleanup_path):
                            try:
                                os.remove(self.cleanup_path)
                                logger.info(f"Cleaned up temporary download file: {self.cleanup_path}")
                            except Exception as e:
                                logger.warning(f"Failed to cleanup temp download file: {e}")
            
            return CleanupFileResponse(
                path=temp_path,
                cleanup_path=temp_path if temp_path.startswith(os.path.join(settings.UPLOAD_DIR, "temp_")) else None,
                media_type=metadata["content_type"],
                filename=metadata["original_filename"]
            )
        else:
            # For local files, serve directly
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            
            if not os.path.isfile(file_path):
                file_storage_service.delete_file_metadata(file_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            
            logger.info(f"Serving local file for download: {file_id} ({metadata['original_filename']})")
            
            from fastapi.responses import FileResponse
            return FileResponse(
                path=file_path,
                media_type=metadata["content_type"],
                filename=metadata["original_filename"]
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading file: {str(e)}"
        )


@router.get("/{file_id}/view",
            summary="View a file in browser",
            description="View a file directly in the browser (useful for PDFs)")
async def view_file(file_id: str):
    """
    View a file directly in the browser. For S3 files, redirects to S3 URL if public, otherwise serves temporarily.
    
    - **file_id**: The unique identifier of the file
    """
    try:
        from src.services.storage import file_storage_service
        
        # Get file metadata
        metadata = file_storage_service.get_file_metadata(file_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        storage_type = metadata.get("storage_type", "local")
        
        if storage_type == "s3":
            # For S3 files, try to redirect to public URL first
            file_url = metadata.get("file_url")
            if file_url:
                logger.info(f"Redirecting to S3 URL for viewing: {file_id} ({metadata['original_filename']})")
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=file_url)
            else:
                # Fallback to temporary download if no public URL
                temp_path = file_storage_service.get_file_path_for_processing(file_id)
                logger.info(f"Serving S3 file for viewing: {file_id} ({metadata['original_filename']})")
                
                from fastapi.responses import FileResponse
                return FileResponse(
                    path=temp_path,
                    media_type=metadata["content_type"],
                    filename=metadata["original_filename"]
                )
        else:
            # For local files, serve directly
            unique_filename = metadata["unique_filename"]
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            
            if not os.path.isfile(file_path):
                file_storage_service.delete_file_metadata(file_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            
            logger.info(f"Serving local file for viewing: {file_id} ({metadata['original_filename']})")
            
            from fastapi.responses import FileResponse
            return FileResponse(
                path=file_path,
                media_type=metadata["content_type"]
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error viewing file {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error viewing file: {str(e)}"
        )


@router.delete("/delete/{file_id}",
               summary="Delete a file",
               description="Delete a file by its ID from storage and vector database")
async def delete_file(file_id: str):
    """
    Delete a file by its unique ID from both file storage and vector database.
    
    - **file_id**: The unique identifier of the file to delete
    """
    try:
        from src.services.storage import file_storage_service
        
        # Get file metadata to check if file exists
        metadata = file_storage_service.get_file_metadata(file_id)
        if not metadata:
            logger.error(f"File not found for deletion: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        deleted_filename = metadata["original_filename"]
        
        # Delete the file using the storage service (handles both S3 and local)
        try:
            success = file_storage_service.delete_file(file_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete file from storage"
                )
            
            stage_logger.info(ProcessingStage.UPLOADING, f"File deleted from storage: {deleted_filename}")
            
        except Exception as delete_error:
            logger.error(f"Error deleting file {file_id}: {str(delete_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file from storage: {str(delete_error)}"
            )
        
        # Try to delete from vector database (ChromaDB)
        try:
            from src.services.storage import chroma_service
            
            # Delete document embeddings from vector store
            result = chroma_service.delete_documents_by_file_id(file_id)
            deleted_count = result.get("deleted_count", 0)
            
            if deleted_count > 0:
                stage_logger.info(ProcessingStage.INDEXING, 
                                f"Deleted {deleted_count} document chunks from vector store for file: {file_id}")
            else:
                stage_logger.warning(ProcessingStage.INDEXING, 
                                   f"No document chunks found in vector store for file: {file_id}")
                
        except Exception as vector_error:
            # Log the error but don't fail the entire operation
            # The file has been deleted from storage, which is the primary goal
            logger.warning(f"Failed to delete from vector store for file {file_id}: {str(vector_error)}")
            stage_logger.warning(ProcessingStage.INDEXING, 
                               f"Vector store cleanup failed for {file_id}: {str(vector_error)}")
        
        logger.info(f"File successfully deleted: {file_id} ({deleted_filename})")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"File '{deleted_filename}' deleted successfully",
                "file_id": file_id,
                "filename": deleted_filename,
                "status": "deleted"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting file {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during file deletion: {str(e)}"
        )



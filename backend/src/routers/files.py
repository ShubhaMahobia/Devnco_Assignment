import os
import uuid
import shutil
import asyncio
import json
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from config import settings
from src.schemas.file_upload import FileUploadResponse, FileInfo, UploadError
from src.services.ingestion import document_processor
from src.services.progress_tracker import progress_tracker, ProgressStage as ProgressStageEnum
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

async def process_document_with_progress(file: UploadFile, file_id: str) -> Dict[str, Any]:
    """Process document with progress tracking"""
    try:
        # Update progress: Uploading
        progress_tracker.update_stage(file_id, ProgressStageEnum.UPLOADING, "Saving file to storage...")
        
        # Step 1: Upload and save file
        file_content = await file.read()
        file_info = document_processor.storage_service.save_file(file_content, file.filename)
        # Override the file_id with our progress tracking ID
        file_info["file_id"] = file_id
        
        # Update progress: Extracting
        progress_tracker.update_stage(file_id, ProgressStageEnum.EXTRACTING, "Extracting text from document...")
        
        # Step 2: Extract text using LangChain document loaders
        documents = await document_processor.extract_text(file_info["file_path"], file_info["content_type"])
        
        # Update progress: Chunking
        progress_tracker.update_stage(file_id, ProgressStageEnum.CHUNKING, f"Creating chunks from {len(documents)} document(s)...")
        
        # Step 3: Create chunks with metadata
        chunks = document_processor.create_chunks(documents, file_info["file_id"], file.filename)
        
        # Update progress: Embedding
        progress_tracker.update_stage(file_id, ProgressStageEnum.EMBEDDING, f"Generating embeddings for {len(chunks)} chunks...")
        
        # Step 4: Generate embeddings
        embeddings = await document_processor.generate_embeddings(chunks)
        
        # Update progress: Indexing
        progress_tracker.update_stage(file_id, ProgressStageEnum.INDEXING, "Indexing document in vector database...")
        
        # Step 5: Index document in ChromaDB
        index_info = await document_processor.index_document(file_info["file_id"], chunks, embeddings)
        
        # Calculate total text length from all documents
        total_text_length = sum(len(doc.page_content) for doc in documents)
        
        # Compile final result
        result = {
            "file_info": file_info,
            "documents": [
                {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata
                } for doc in documents
            ],
            "processing_stats": {
                "documents_count": len(documents),
                "text_length": total_text_length,
                "chunks_count": len(chunks) if chunks else 0,
                "embeddings_count": len(embeddings) if embeddings else 0
            },
            "index_info": index_info,
            "status": "completed"
        }
        
        return result
        
    except Exception as e:
        stage_logger.error(ProcessingStage.FAILED, f"Document processing with progress failed: {str(e)}")
        raise

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
        
        # Generate file ID for progress tracking
        file_id = str(uuid.uuid4())
        
        # Initialize progress tracking
        progress_tracker.start_processing(file_id, file.filename)
        
        # Start the complete processing pipeline
        stage_logger.info(ProcessingStage.UPLOADING, f"Starting document processing pipeline for: {file.filename}")
        
        try:
            # Process the document through the complete pipeline with progress tracking
            processing_result = await process_document_with_progress(file, file_id)
            
            # Create enhanced response with processing information
            response = FileUploadResponse(
                file_id=processing_result["file_info"]["file_id"],
                filename=file.filename,
                file_path=processing_result["file_info"]["file_path"],
                file_size=file_size,
                content_type=processing_result["file_info"]["content_type"],
                status="processed"  # Changed from "uploaded" to "processed"
            )
            
            # Mark processing as completed
            progress_tracker.complete_processing(file_id, f"Document processed successfully with {processing_result['processing_stats']['chunks_count']} chunks")
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"File upload and processing completed successfully: {file.filename} "
                            f"({processing_result['processing_stats']['chunks_count']} chunks indexed)")
            
            return response
            
        except Exception as processing_error:
            # Mark processing as failed
            progress_tracker.fail_processing(file_id, f"Processing failed: {str(processing_error)}")
            
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
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            
            # Check if file still exists on disk
            if os.path.isfile(file_path):
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
                logger.warning(f"File {unique_filename} missing from disk, cleaning up metadata")
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
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Check if file exists on disk
        if not os.path.isfile(file_path):
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
    Download a file by its unique ID using metadata system.
    
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
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Check if file exists on disk
        if not os.path.isfile(file_path):
            # Clean up orphaned metadata
            file_storage_service.delete_file_metadata(file_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        logger.info(f"Serving file for download: {file_id} ({metadata['original_filename']})")
        
        # Return file response with original filename
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path,
            media_type=metadata["content_type"],
            filename=metadata["original_filename"]  # Use original filename for download
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading file: {str(e)}"
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
        if not os.path.exists(settings.UPLOAD_DIR):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        file_found = False
        deleted_filename = None
        
        # Find and delete the file
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename.startswith(file_id):
                file_path = os.path.join(settings.UPLOAD_DIR, filename)
                if os.path.isfile(file_path):
                    try:
                        # Delete the physical file
                        os.remove(file_path)
                        file_found = True
                        deleted_filename = filename
                        stage_logger.info(ProcessingStage.UPLOADING, f"File deleted from storage: {filename}")
                        break
                    except OSError as e:
                        logger.error(f"Error deleting file {filename}: {str(e)}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to delete file from storage: {str(e)}"
                        )
        
        if not file_found:
            logger.error(f"File not found for deletion: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Try to delete from vector database (ChromaDB)
        try:
            from src.services.storage import vector_store
            
            # Delete document embeddings from vector store
            deleted_count = await vector_store.delete_document(file_id)
            
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


@router.get("/progress/{file_id}",
            summary="Get upload progress via Server-Sent Events",
            description="Stream real-time progress updates for file processing")
async def get_upload_progress(file_id: str):
    """
    Get real-time progress updates for file processing via Server-Sent Events.
    
    - **file_id**: The unique identifier of the file being processed
    """
    async def event_generator():
        queue = asyncio.Queue()
        progress_tracker.add_listener(file_id, queue)
        
        try:
            # Send initial progress if available
            initial_progress = progress_tracker.get_progress(file_id)
            if initial_progress:
                yield {
                    "event": "progress",
                    "data": json.dumps(initial_progress)
                }
            
            # Stream updates
            while True:
                try:
                    # Wait for progress update with timeout
                    progress_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    yield {
                        "event": "progress", 
                        "data": json.dumps(progress_data)
                    }
                    
                    # Stop streaming if processing is completed or failed
                    if progress_data.get("current_stage") in ["completed", "failed"]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send keep-alive message
                    yield {
                        "event": "keepalive",
                        "data": json.dumps({"timestamp": datetime.now().isoformat()})
                    }
                    continue
                    
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            progress_tracker.remove_listener(file_id, queue)
    
    return EventSourceResponse(event_generator())


@router.get("/progress/{file_id}/status",
            summary="Get current upload progress status",
            description="Get the current progress status for file processing")
async def get_progress_status(file_id: str):
    """
    Get the current progress status for file processing.
    
    - **file_id**: The unique identifier of the file being processed
    """
    progress = progress_tracker.get_progress(file_id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress not found for this file ID"
        )
    
    return JSONResponse(content=progress)
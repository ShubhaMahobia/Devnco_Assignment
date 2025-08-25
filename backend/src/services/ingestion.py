import asyncio
from typing import Dict, Any, List, Optional
from fastapi import UploadFile
from pathlib import Path
from datetime import datetime

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredFileLoader
)
from langchain_core.documents import Document

from src.services.storage import file_storage_service
from src.utils.logger import stage_logger, ProcessingStage

class DocumentProcessor:
    """Service for processing documents through the complete pipeline"""
    
    def __init__(self):
        self.storage_service = file_storage_service
    
    async def extract_text(self, file_path: str, content_type: str) -> List[Document]:
        """Extract text from different file types using LangChain document loaders"""
        with stage_logger.time_stage(ProcessingStage.EXTRACTING, f"extract_{Path(file_path).name}"):
            documents = []
            
            try:
                if content_type == 'text/plain':
                    # Use TextLoader for plain text files
                    loader = TextLoader(file_path, encoding='utf-8')
                    documents = loader.load()
                    
                elif content_type == 'application/pdf':
                    # Use PyPDFLoader for PDF files
                    loader = PyPDFLoader(file_path)
                    documents = loader.load()
                    
                elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    # Use Docx2txtLoader for DOCX files
                    loader = Docx2txtLoader(file_path)
                    documents = loader.load()
                    
                elif content_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv']:
                    # Use UnstructuredFileLoader for other supported formats
                    loader = UnstructuredFileLoader(file_path)
                    documents = loader.load()
                    
                else:
                    # Fallback to UnstructuredFileLoader for unsupported types
                    try:
                        loader = UnstructuredFileLoader(file_path)
                        documents = loader.load()
                    except Exception as fallback_error:
                        raise ValueError(f"Unsupported content type: {content_type}. Fallback loader failed: {str(fallback_error)}")
                
                # Add metadata to documents
                for doc in documents:
                    doc.metadata.update({
                        'file_path': file_path,
                        'content_type': content_type,
                        'processed_at': datetime.now().isoformat()
                    })
                
                total_chars = sum(len(doc.page_content) for doc in documents)
                stage_logger.info(ProcessingStage.EXTRACTING, 
                                f"Extracted {total_chars} characters from {len(documents)} document(s)")
                return documents
                
            except Exception as e:
                stage_logger.error(ProcessingStage.EXTRACTING, f"Failed to extract text: {str(e)}")
                raise
    
    def create_chunks(self, documents: List[Document], chunk_size: int = 1000, overlap: int = 200) -> List[Document]:
        """Split documents into chunks"""
        with stage_logger.time_stage(ProcessingStage.CHUNKING, "create_chunks"):
            # For now, return the documents as-is
            # TODO: Implement proper chunking using LangChain text splitters
            return documents
    
    async def generate_embeddings(self, chunks: List[Document]) -> List[List[float]]:
        """Generate embeddings for document chunks"""
        with stage_logger.time_stage(ProcessingStage.EMBEDDING, f"embed_{len(chunks)}_chunks"): 
            # TODO: Implement embedding generation using LangChain embeddings
            return None
    
    async def index_document(self, file_id: str, chunks: List[Document], embeddings: List[List[float]]) -> Dict[str, Any]:
        """Index document chunks and embeddings"""
        with stage_logger.time_stage(ProcessingStage.INDEXING, f"index_{file_id}"):
            # TODO: Implement document indexing using vector store
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Indexed document {file_id} with {len(chunks)} chunks")
            return None
    
    async def process_document(self, file: UploadFile) -> Dict[str, Any]:
        """Complete document processing pipeline"""
        try:
            # Step 1: Upload and save file
            stage_logger.info(ProcessingStage.UPLOADING, f"Starting document processing for: {file.filename}")
            
            file_content = await file.read()
            file_info = self.storage_service.save_file(file_content, file.filename)
            
            # Step 2: Extract text using LangChain document loaders
            documents = await self.extract_text(file_info["file_path"], file_info["content_type"])
            
            # Step 3: Create chunks (now working with Document objects)
            chunks = self.create_chunks(documents)
            
            # Step 4: Generate embeddings
            embeddings = await self.generate_embeddings(chunks)
            
            # Step 5: Index document
            index_info = await self.index_document(file_info["file_id"], chunks, embeddings)
            
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
            
            # Log timing summary
            stage_logger.log_timing_summary()
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Document processing completed for: {file.filename}")
            
            return result
            
        except Exception as e:
            stage_logger.error(ProcessingStage.FAILED, f"Document processing failed: {str(e)}")
            # Clean up uploaded file if processing failed
            if 'file_info' in locals():
                self.storage_service.delete_file(file_info["file_id"])
            raise

# Global instance
document_processor = DocumentProcessor()

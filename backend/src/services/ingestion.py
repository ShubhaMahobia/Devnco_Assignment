import asyncio
import os
from typing import Dict, Any, List, Optional
from fastapi import UploadFile
from pathlib import Path
from datetime import datetime
import uuid
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredFileLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.services.storage import file_storage_service, chroma_service
from src.utils.logger import stage_logger, ProcessingStage
from config import settings

class DocumentProcessor:
    """Service for processing documents through the complete pipeline"""
    
    def __init__(self):
        self.storage_service = file_storage_service
        self.vector_store = chroma_service
    
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
    
    def create_chunks(self, documents: List[Document], doc_id: str, doc_name: str, 
                     chunk_size: int = None, overlap: int = None) -> List[Document]:
        """Split documents into chunks using RecursiveCharacterTextSplitter with comprehensive metadata"""
        with stage_logger.time_stage(ProcessingStage.CHUNKING, "create_chunks"):
            # Use config values if not provided
            chunk_size = chunk_size or settings.CHUNK_SIZE
            overlap = overlap or settings.CHUNK_OVERLAP
            
            # Initialize the text splitter with configurable parameters
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            
            # Split all documents into chunks with metadata
            all_chunks = []
            timestamp = datetime.now().isoformat()
            
            for doc_index, doc in enumerate(documents):
                chunks = text_splitter.split_documents([doc])
                
                # Add comprehensive metadata to each chunk
                for chunk_index, chunk in enumerate(chunks):
                    chunk_id = str(uuid.uuid4())
                    
                    # Get page number from original document metadata or calculate from doc_index
                    page_number = doc.metadata.get('page', doc_index + 1)
                    
                    # Update chunk metadata with all required fields
                    chunk.metadata.update({
                        'doc_id': doc_id,
                        'doc_name': doc_name,
                        'page': page_number,
                        'chunk_id': chunk_id,
                        'ts': timestamp,
                        'chunk_index': chunk_index,
                        'total_chunks_in_doc': len(chunks),
                        'chunk_size': chunk_size,
                        'chunk_overlap': overlap
                    })
                    
                    all_chunks.append(chunk)
            
            stage_logger.info(ProcessingStage.CHUNKING, 
                            f"Split {len(documents)} documents into {len(all_chunks)} chunks "
                            f"(chunk_size={chunk_size}, overlap={overlap}) for doc: {doc_name}")
            return all_chunks
    
    async def generate_embeddings(self, chunks: List[Document]) -> List[List[float]]:
        """Generate embeddings for document chunks using BGE model"""
        with stage_logger.time_stage(ProcessingStage.EMBEDDING, f"embed_{len(chunks)}_chunks"): 
            try:
                embeddings_model = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={'device': settings.EMBEDDING_DEVICE},
                    encode_kwargs={'normalize_embeddings': settings.NORMALIZE_EMBEDDINGS}
                )
                
                texts = [chunk.page_content for chunk in chunks]
                
                # Generate embeddings for all chunks
                embeddings = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    embeddings_model.embed_documents,
                    texts
                )
                
                stage_logger.info(ProcessingStage.EMBEDDING, 
                                f"Generated embeddings for {len(chunks)} chunks using {settings.EMBEDDING_MODEL}")
                
                return embeddings
                
            except Exception as e:
                stage_logger.error(ProcessingStage.EMBEDDING, f"Error generating embeddings: {str(e)}")
                raise Exception(f"Failed to generate embeddings: {str(e)}")
    
    async def index_document(self, file_id: str, chunks: List[Document], embeddings: List[List[float]]) -> Dict[str, Any]:
        """Index document chunks and embeddings using ChromaDB"""
        with stage_logger.time_stage(ProcessingStage.INDEXING, f"index_{file_id}"):
            try:
                # Use ChromaDB service to index the documents
                result = await self.vector_store.index_documents(file_id, chunks, embeddings)
                
                stage_logger.info(ProcessingStage.INDEXING, 
                                f"Successfully indexed document {file_id} with {len(chunks)} chunks in ChromaDB")
                
                return result
                
            except Exception as e:
                stage_logger.error(ProcessingStage.INDEXING, 
                                 f"Failed to index document {file_id}: {str(e)}")
                raise Exception(f"Document indexing failed: {str(e)}")
    
    async def process_document(self, file: UploadFile) -> Dict[str, Any]:
        """Complete document processing pipeline"""
        try:
            # Step 1: Upload and save file
            stage_logger.info(ProcessingStage.UPLOADING, f"Starting document processing for: {file.filename}")
            
            file_content = await file.read()
            file_info = self.storage_service.save_file(file_content, file.filename)
            
            # Step 2: Extract text using LangChain document loaders
            documents = await self.extract_text(file_info["file_path"], file_info["content_type"])
            
            # Step 3: Create chunks with metadata
            chunks = self.create_chunks(documents, file_info["file_id"], file.filename)
            
            # Step 4: Generate embeddings
            embeddings = await self.generate_embeddings(chunks)
            
            # Step 5: Index document in ChromaDB
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
    
    def reset_application_data(self) -> Dict[str, Any]:
        """Reset all application data - files and database"""
        try:
            # Reset ChromaDB
            db_result = self.vector_store.reset_database()
            
            # Delete all uploaded files
            import shutil
            if os.path.exists(settings.UPLOAD_DIR):
                shutil.rmtree(settings.UPLOAD_DIR)
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            
            result = {
                "database_reset": db_result,
                "files_cleared": True,
                "status": "success",
                "message": "Application data has been completely reset"
            }
            
            stage_logger.info(ProcessingStage.INDEXING, "Application data reset completed")
            
            return result
            
        except Exception as e:
            stage_logger.error(ProcessingStage.FAILED, f"Application reset failed: {str(e)}")
            raise Exception(f"Application reset failed: {str(e)}")

# Global instance
document_processor = DocumentProcessor()

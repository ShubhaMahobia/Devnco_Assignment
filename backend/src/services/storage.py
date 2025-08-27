import os
import uuid
import shutil
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document

from config import settings
from src.utils.logger import stage_logger, ProcessingStage

class FileStorageService:
    """Service for handling file storage operations"""
    
    def __init__(self):
        # Ensure upload directory exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        self.metadata_file = os.path.join(settings.UPLOAD_DIR, "file_metadata.json")
        self._ensure_metadata_file()
    
    def _ensure_metadata_file(self):
        """Ensure metadata file exists"""
        if not os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'w') as f:
                json.dump({}, f)
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load file metadata"""
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save file metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _add_file_metadata(self, file_id: str, original_filename: str, unique_filename: str, 
                          file_size: int, content_type: str, upload_timestamp: str):
        """Add metadata for a file"""
        metadata = self._load_metadata()
        metadata[file_id] = {
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "file_size": file_size,
            "content_type": content_type,
            "upload_timestamp": upload_timestamp
        }
        self._save_metadata(metadata)
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific file"""
        metadata = self._load_metadata()
        return metadata.get(file_id)
    
    def get_all_files_metadata(self) -> Dict[str, Any]:
        """Get metadata for all files"""
        return self._load_metadata()
    
    def delete_file_metadata(self, file_id: str):
        """Delete metadata for a file"""
        metadata = self._load_metadata()
        if file_id in metadata:
            del metadata[file_id]
            self._save_metadata(metadata)
    
    def save_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Save file to storage and return file information"""
        try:
            # Generate unique file ID and filename
            file_id = str(uuid.uuid4())
            file_extension = Path(filename).suffix.lower()
            unique_filename = f"{file_id}{file_extension}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            
            # Save file to disk
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
            
            # Determine content type
            content_type_map = {
                '.txt': 'text/plain',
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            content_type = content_type_map.get(file_extension, 'application/octet-stream')
            
            upload_timestamp = datetime.now().isoformat()
            
            file_info = {
                "file_id": file_id,
                "filename": filename,
                "unique_filename": unique_filename,
                "file_path": file_path,
                "file_size": len(file_content),
                "content_type": content_type,
                "upload_timestamp": upload_timestamp
            }
            
            # Store metadata
            self._add_file_metadata(
                file_id=file_id,
                original_filename=filename,
                unique_filename=unique_filename,
                file_size=len(file_content),
                content_type=content_type,
                upload_timestamp=upload_timestamp
            )
            
            stage_logger.info(ProcessingStage.UPLOADING, 
                            f"File saved: {filename} -> {unique_filename}")
            return file_info
            
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Failed to save file: {str(e)}")
            raise
    
    def delete_file(self, file_id: str) -> bool:
        """Delete file from storage and metadata"""
        try:
            # Get metadata first to find the unique filename
            metadata = self.get_file_metadata(file_id)
            if metadata:
                unique_filename = metadata["unique_filename"]
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    stage_logger.info(ProcessingStage.UPLOADING, f"Deleted file: {unique_filename}")
                
                # Remove metadata
                self.delete_file_metadata(file_id)
                return True
            else:
                # Fallback: try to find file by ID prefix (for legacy files)
                for filename in os.listdir(settings.UPLOAD_DIR):
                    if filename.startswith(file_id) and filename != "file_metadata.json":
                        file_path = os.path.join(settings.UPLOAD_DIR, filename)
                        os.remove(file_path)
                        stage_logger.info(ProcessingStage.UPLOADING, f"Deleted legacy file: {filename}")
                        return True
            return False
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Failed to delete file: {str(e)}")
            raise

class ChromaDBService:
    """Service for managing ChromaDB vector store operations"""
    
    def __init__(self):
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the collection exists, create if not"""
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Connected to existing ChromaDB collection: {self.collection_name}")
        except Exception:
            # Collection doesn't exist, create it
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Document chunks and embeddings for RAG application"}
            )
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Created new ChromaDB collection: {self.collection_name}")
    
    async def index_documents(self, file_id: str, chunks: List[Document], embeddings: List[List[float]]) -> Dict[str, Any]:
        """Index document chunks and embeddings in ChromaDB"""
        try:
            if len(chunks) != len(embeddings):
                raise ValueError("Number of chunks and embeddings must match")
            
            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Create unique ID for each chunk
                chunk_id = f"{file_id}_{i}_{chunk.metadata.get('chunk_id', str(uuid.uuid4()))}"
                ids.append(chunk_id)
                documents.append(chunk.page_content)
                
                # Prepare metadata (ChromaDB requires all values to be strings, numbers, or booleans)
                metadata = {}
                for key, value in chunk.metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        metadata[key] = value
                    else:
                        metadata[key] = str(value)
                
                metadatas.append(metadata)
            
            # Add documents to ChromaDB
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            # Get collection stats
            collection_count = self.collection.count()
            
            result = {
                "indexed_chunks": len(chunks),
                "collection_total_documents": collection_count,
                "file_id": file_id,
                "status": "success"
            }
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Successfully indexed {len(chunks)} chunks for file {file_id}. "
                            f"Collection now contains {collection_count} documents")
            
            return result
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, 
                             f"Failed to index documents in ChromaDB: {str(e)}")
            raise Exception(f"ChromaDB indexing failed: {str(e)}")
    
    async def search_similar_documents(self, query_embedding: List[float], n_results: int = 5, 
                                     file_id: Optional[str] = None) -> Dict[str, Any]:
        """Search for similar documents using embeddings"""
        try:
            where_clause = {"doc_id": file_id} if file_id else None
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            return {
                "documents": results["documents"][0] if results["documents"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
                "distances": results["distances"][0] if results["distances"] else [],
                "count": len(results["documents"][0]) if results["documents"] else 0
            }
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Search failed: {str(e)}")
            raise Exception(f"ChromaDB search failed: {str(e)}")
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the ChromaDB collection"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "database_path": settings.CHROMA_DB_PATH
            }
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Failed to get collection info: {str(e)}")
            raise
    
    def delete_documents_by_file_id(self, file_id: str) -> Dict[str, Any]:
        """Delete all documents associated with a specific file ID"""
        try:
            # Query to find all documents with the specific file_id
            results = self.collection.get(
                where={"doc_id": file_id},
                include=["metadatas"]
            )
            
            if results["ids"]:
                # Delete the documents
                self.collection.delete(ids=results["ids"])
                deleted_count = len(results["ids"])
                
                stage_logger.info(ProcessingStage.INDEXING, 
                                f"Deleted {deleted_count} documents for file {file_id}")
                
                return {
                    "deleted_count": deleted_count,
                    "file_id": file_id,
                    "status": "success"
                }
            else:
                return {
                    "deleted_count": 0,
                    "file_id": file_id,
                    "status": "no_documents_found"
                }
                
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, 
                             f"Failed to delete documents for file {file_id}: {str(e)}")
            raise
    
    def reset_database(self) -> Dict[str, Any]:
        """Reset the entire ChromaDB database - WARNING: This deletes all data"""
        try:
            # Delete the collection
            self.client.delete_collection(name=self.collection_name)
            
            # Recreate the collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Document chunks and embeddings for RAG application"}
            )
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Database reset completed. Collection '{self.collection_name}' recreated")
            
            return {
                "status": "success",
                "message": f"Database reset completed. Collection '{self.collection_name}' recreated",
                "collection_count": 0
            }
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Database reset failed: {str(e)}")
            raise Exception(f"Database reset failed: {str(e)}")

# Global service instances
file_storage_service = FileStorageService()
chroma_service = ChromaDBService()
import os
import uuid
import shutil
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document
import io

from config import settings
from src.utils.logger import stage_logger, ProcessingStage


class S3StorageService:
    """Service for handling AWS S3 file operations"""
    
    def __init__(self):
        """Initialize S3 client"""
        try:
            # Initialize S3 client with credentials from environment or IAM role
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.S3_REGION
                )
            else:
                # Use default credential chain (IAM role, AWS CLI config, etc.)
                self.s3_client = boto3.client('s3', region_name=settings.S3_REGION)
            
            self.bucket_name = settings.S3_BUCKET_NAME
            self.bucket_folder = settings.S3_BUCKET_FOLDER
            
            stage_logger.info(ProcessingStage.UPLOADING, 
                            f"S3 service initialized for bucket: {self.bucket_name}")
            
        except NoCredentialsError:
            stage_logger.error(ProcessingStage.FAILED, 
                             "AWS credentials not found. Please configure AWS credentials.")
            raise Exception("AWS credentials not found")
        except Exception as e:
            stage_logger.error(ProcessingStage.FAILED, f"Failed to initialize S3 client: {str(e)}")
            raise
    
    def _get_s3_key(self, filename: str) -> str:
        """Generate S3 key with folder prefix"""
        return f"{self.bucket_folder}/{filename}"
    
    def upload_file(self, file_content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """Upload file to S3 and return file information"""
        try:
            s3_key = self._get_s3_key(filename)
            
            # Upload file to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
                # Note: ACL removed since bucket doesn't allow ACLs
                # Public access is controlled at bucket level
            )
            
            # Generate public URL
            file_url = f"https://{self.bucket_name}.s3.{settings.S3_REGION}.amazonaws.com/{s3_key}"
            
            stage_logger.info(ProcessingStage.UPLOADING, 
                            f"File uploaded to S3: {filename} -> {s3_key}")
            
            return {
                "s3_key": s3_key,
                "file_url": file_url,
                "bucket_name": self.bucket_name,
                "file_size": len(file_content)
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            stage_logger.error(ProcessingStage.UPLOADING, 
                             f"S3 upload failed ({error_code}): {str(e)}")
            raise Exception(f"S3 upload failed: {str(e)}")
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Unexpected S3 upload error: {str(e)}")
            raise
    
    def download_file(self, filename: str) -> bytes:
        """Download file from S3"""
        try:
            s3_key = self._get_s3_key(filename)
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            file_content = response['Body'].read()
            stage_logger.info(ProcessingStage.UPLOADING, f"Downloaded {len(file_content)} bytes from S3: {s3_key}")
            return file_content
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                stage_logger.error(ProcessingStage.UPLOADING, f"File not found in S3: {s3_key}")
                raise FileNotFoundError(f"File not found in S3: {filename}")
            else:
                stage_logger.error(ProcessingStage.UPLOADING, f"S3 download failed: {str(e)}")
                raise Exception(f"S3 download failed: {str(e)}")
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Unexpected S3 download error: {str(e)}")
            raise
    
    def delete_file(self, filename: str) -> bool:
        """Delete file from S3"""
        try:
            s3_key = self._get_s3_key(filename)
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            stage_logger.info(ProcessingStage.UPLOADING, f"File deleted from S3: {s3_key}")
            return True
            
        except ClientError as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"S3 delete failed: {str(e)}")
            return False
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Unexpected S3 delete error: {str(e)}")
            return False
    
    def file_exists(self, filename: str) -> bool:
        """Check if file exists in S3"""
        try:
            s3_key = self._get_s3_key(filename)
            
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                stage_logger.error(ProcessingStage.UPLOADING, f"S3 head_object failed: {str(e)}")
                raise Exception(f"S3 file check failed: {str(e)}")
    
    def get_file_info(self, filename: str) -> Dict[str, Any]:
        """Get file metadata from S3"""
        try:
            s3_key = self._get_s3_key(filename)
            
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                "file_size": response.get('ContentLength', 0),
                "content_type": response.get('ContentType', 'application/octet-stream'),
                "last_modified": response.get('LastModified'),
                "etag": response.get('ETag', '').strip('"'),
                "s3_key": s3_key,
                "file_url": f"https://{self.bucket_name}.s3.{settings.S3_REGION}.amazonaws.com/{s3_key}"
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"File not found in S3: {filename}")
            else:
                stage_logger.error(ProcessingStage.UPLOADING, f"S3 head_object failed: {str(e)}")
                raise Exception(f"S3 file info failed: {str(e)}")


class FileStorageService:
    """Service for handling file storage operations with S3 support"""
    
    def __init__(self):
        # Initialize S3 service if enabled
        if settings.USE_S3_STORAGE:
            try:
                self.s3_service = S3StorageService()
                stage_logger.info(ProcessingStage.UPLOADING, "FileStorageService initialized with S3 storage")
            except Exception as e:
                stage_logger.error(ProcessingStage.FAILED, f"Failed to initialize S3 storage: {str(e)}")
                stage_logger.info(ProcessingStage.UPLOADING, "Falling back to local storage")
                settings.USE_S3_STORAGE = False
                self.s3_service = None
        else:
            self.s3_service = None
            stage_logger.info(ProcessingStage.UPLOADING, "FileStorageService initialized with local storage")
        
        # Ensure upload directory exists (for local storage or temporary processing)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        self.metadata_file = os.path.join(settings.UPLOAD_DIR, "file_metadata.json")
        self.s3_metadata_key = "file_metadata.json"  # S3 key for metadata file
        self._ensure_metadata_file()
    
    def _ensure_metadata_file(self):
        """Ensure metadata file exists locally and sync from S3 if using S3 storage"""
        if settings.USE_S3_STORAGE and self.s3_service:
            # Try to download metadata from S3 first
            try:
                metadata_content = self.s3_service.download_file(self.s3_metadata_key)
                with open(self.metadata_file, 'wb') as f:
                    f.write(metadata_content)
                stage_logger.info(ProcessingStage.UPLOADING, "Downloaded metadata from S3")
            except FileNotFoundError:
                # Metadata doesn't exist in S3, create empty local file
                with open(self.metadata_file, 'w') as f:
                    json.dump({}, f)
                stage_logger.info(ProcessingStage.UPLOADING, "Created new metadata file")
            except Exception as e:
                stage_logger.warning(ProcessingStage.UPLOADING, f"Failed to download metadata from S3: {e}")
                # Create empty local file as fallback
                with open(self.metadata_file, 'w') as f:
                    json.dump({}, f)
        else:
            # Local storage - just ensure local file exists
            if not os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'w') as f:
                    json.dump({}, f)
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load file metadata from local file"""
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save file metadata locally and to S3 if using S3 storage"""
        # Save locally first
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Also save to S3 if using S3 storage
        if settings.USE_S3_STORAGE and self.s3_service:
            try:
                with open(self.metadata_file, 'rb') as f:
                    metadata_content = f.read()
                self.s3_service.upload_file(metadata_content, self.s3_metadata_key, 'application/json')
                stage_logger.info(ProcessingStage.UPLOADING, "Metadata synced to S3")
            except Exception as e:
                stage_logger.warning(ProcessingStage.UPLOADING, f"Failed to sync metadata to S3: {e}")
    
    def _add_file_metadata(self, file_id: str, original_filename: str, unique_filename: str, 
                          file_size: int, content_type: str, upload_timestamp: str,
                          s3_key: str = None, file_url: str = None, storage_type: str = "local"):
        """Add metadata for a file"""
        metadata = self._load_metadata()
        file_metadata = {
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "file_size": file_size,
            "content_type": content_type,
            "upload_timestamp": upload_timestamp,
            "storage_type": storage_type
        }
        
        # Add S3-specific metadata if applicable
        if storage_type == "s3" and s3_key and file_url:
            file_metadata.update({
                "s3_key": s3_key,
                "file_url": file_url
            })
        
        metadata[file_id] = file_metadata
        self._save_metadata(metadata)
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific file"""
        metadata = self._load_metadata()
        return metadata.get(file_id)
    
    def get_all_files_metadata(self) -> Dict[str, Any]:
        """Get metadata for all files, refreshing from S3 if needed"""
        # For S3 storage, try to refresh metadata from S3 first
        if settings.USE_S3_STORAGE and self.s3_service:
            try:
                metadata_content = self.s3_service.download_file(self.s3_metadata_key)
                with open(self.metadata_file, 'wb') as f:
                    f.write(metadata_content)
                stage_logger.info(ProcessingStage.UPLOADING, "Refreshed metadata from S3")
            except FileNotFoundError:
                stage_logger.info(ProcessingStage.UPLOADING, "No metadata file found in S3")
            except Exception as e:
                stage_logger.warning(ProcessingStage.UPLOADING, f"Failed to refresh metadata from S3: {e}")
        
        return self._load_metadata()
    
    def delete_file_metadata(self, file_id: str):
        """Delete metadata for a file"""
        metadata = self._load_metadata()
        if file_id in metadata:
            del metadata[file_id]
            self._save_metadata(metadata)
    
    def save_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Save file to storage (S3 or local) and return file information"""
        try:
            # Generate unique file ID and filename
            file_id = str(uuid.uuid4())
            file_extension = Path(filename).suffix.lower()
            unique_filename = f"{file_id}{file_extension}"
            
            # Determine content type
            content_type_map = {
                '.txt': 'text/plain',
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            content_type = content_type_map.get(file_extension, 'application/octet-stream')
            
            upload_timestamp = datetime.now().isoformat()
            
            if settings.USE_S3_STORAGE and self.s3_service:
                # Upload to S3
                s3_result = self.s3_service.upload_file(file_content, unique_filename, content_type)
                
                file_info = {
                    "file_id": file_id,
                    "filename": filename,
                    "unique_filename": unique_filename,
                    "file_path": s3_result["file_url"],  # S3 URL instead of local path
                    "s3_key": s3_result["s3_key"],
                    "file_size": len(file_content),
                    "content_type": content_type,
                    "upload_timestamp": upload_timestamp,
                    "storage_type": "s3"
                }
                
                # Store metadata with S3 information
                self._add_file_metadata(
                    file_id=file_id,
                    original_filename=filename,
                    unique_filename=unique_filename,
                    file_size=len(file_content),
                    content_type=content_type,
                    upload_timestamp=upload_timestamp,
                    s3_key=s3_result["s3_key"],
                    file_url=s3_result["file_url"],
                    storage_type="s3"
                )
                
                stage_logger.info(ProcessingStage.UPLOADING, 
                                f"File saved to S3: {filename} -> {unique_filename}")
            else:
                # Save to local disk
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                file_info = {
                    "file_id": file_id,
                    "filename": filename,
                    "unique_filename": unique_filename,
                    "file_path": file_path,
                    "file_size": len(file_content),
                    "content_type": content_type,
                    "upload_timestamp": upload_timestamp,
                    "storage_type": "local"
                }
                
                # Store metadata
                self._add_file_metadata(
                    file_id=file_id,
                    original_filename=filename,
                    unique_filename=unique_filename,
                    file_size=len(file_content),
                    content_type=content_type,
                    upload_timestamp=upload_timestamp,
                    storage_type="local"
                )
                
                stage_logger.info(ProcessingStage.UPLOADING, 
                                f"File saved locally: {filename} -> {unique_filename}")
            
            return file_info
            
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Failed to save file: {str(e)}")
            raise
    
    def delete_file(self, file_id: str) -> bool:
        """Delete file from storage (S3 or local) and metadata"""
        try:
            # Get metadata first to determine storage type and location
            metadata = self.get_file_metadata(file_id)
            if metadata:
                unique_filename = metadata["unique_filename"]
                storage_type = metadata.get("storage_type", "local")
                
                if storage_type == "s3" and settings.USE_S3_STORAGE and self.s3_service:
                    # Delete from S3
                    success = self.s3_service.delete_file(unique_filename)
                    if success:
                        stage_logger.info(ProcessingStage.UPLOADING, f"Deleted S3 file: {unique_filename}")
                    else:
                        stage_logger.warning(ProcessingStage.UPLOADING, f"Failed to delete S3 file: {unique_filename}")
                else:
                    # Delete from local storage
                    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        stage_logger.info(ProcessingStage.UPLOADING, f"Deleted local file: {unique_filename}")
                
                # Remove metadata
                self.delete_file_metadata(file_id)
                return True
            else:
                # Fallback: try to find file by ID prefix (for legacy files)
                if os.path.exists(settings.UPLOAD_DIR):
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
    
    def get_file_content(self, file_id: str) -> bytes:
        """Get file content from storage (S3 or local)"""
        try:
            metadata = self.get_file_metadata(file_id)
            if not metadata:
                raise FileNotFoundError(f"File metadata not found: {file_id}")
            
            unique_filename = metadata["unique_filename"]
            storage_type = metadata.get("storage_type", "local")
            
            if storage_type == "s3" and settings.USE_S3_STORAGE and self.s3_service:
                # Download from S3
                return self.s3_service.download_file(unique_filename)
            else:
                # Read from local storage
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Local file not found: {file_path}")
                
                with open(file_path, "rb") as f:
                    return f.read()
                    
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Failed to get file content: {str(e)}")
            raise
    
    def get_file_path_for_processing(self, file_id: str) -> str:
        """Get file path for processing. For S3 files, download to temp location."""
        try:
            metadata = self.get_file_metadata(file_id)
            if not metadata:
                raise FileNotFoundError(f"File metadata not found: {file_id}")
            
            unique_filename = metadata["unique_filename"]
            storage_type = metadata.get("storage_type", "local")
            
            if storage_type == "s3" and settings.USE_S3_STORAGE and self.s3_service:
                # Download S3 file to temporary local location for processing
                temp_path = os.path.join(settings.UPLOAD_DIR, f"temp_{unique_filename}")
                file_content = self.s3_service.download_file(unique_filename)
                
                with open(temp_path, "wb") as f:
                    f.write(file_content)
                
                stage_logger.info(ProcessingStage.UPLOADING, 
                                f"Downloaded S3 file for processing: {unique_filename} -> {temp_path}")
                return temp_path
            else:
                # Return local file path
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Local file not found: {file_path}")
                return file_path
                
        except Exception as e:
            stage_logger.error(ProcessingStage.UPLOADING, f"Failed to get file path for processing: {str(e)}")
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
        # Use different collection names for different embedding models
        if settings.USE_OPENAI_EMBEDDINGS:
            self.collection_name = f"{settings.CHROMA_COLLECTION_NAME}_openai_{settings.OPENAI_EMBEDDING_MODEL.replace('-', '_')}"
        else:
            self.collection_name = f"{settings.CHROMA_COLLECTION_NAME}_local_{settings.LOCAL_EMBEDDING_MODEL.replace('/', '_').replace('-', '_')}"
        
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
            error_msg = str(e)
            stage_logger.error(ProcessingStage.INDEXING, 
                             f"Failed to index documents in ChromaDB: {error_msg}")
            
            # Check for dimension mismatch error
            if "expecting embedding with dimension" in error_msg:
                stage_logger.error(ProcessingStage.INDEXING, 
                                 "Embedding dimension mismatch detected. This usually happens when switching between embedding models.")
                stage_logger.info(ProcessingStage.INDEXING, 
                                f"Current collection: {self.collection_name}")
                stage_logger.info(ProcessingStage.INDEXING, 
                                "Consider resetting the database or using a different collection name.")
                
                raise Exception(f"Embedding dimension mismatch: {error_msg}. "
                              "Please reset the database to use the new embedding model, "
                              "or switch back to the previous embedding model.")
            
            raise Exception(f"ChromaDB indexing failed: {error_msg}")
    
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
vector_store = chroma_service  # Alias for backward compatibility
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FileUploadResponse(BaseModel):
    """Response model for file upload"""
    file_id: str = Field(..., description="Unique identifier for the uploaded file")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path where file is stored")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type of the file")
    upload_timestamp: datetime = Field(default_factory=datetime.now, description="When the file was uploaded")
    status: str = Field(default="uploaded", description="Upload status")

class FileInfo(BaseModel):
    """Model for file information"""
    file_id: str
    filename: str
    file_size: int
    content_type: str
    upload_timestamp: datetime
    file_path: str
    
class UploadError(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")

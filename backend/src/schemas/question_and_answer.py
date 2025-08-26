from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field

class QuestionRequest(BaseModel):
    """Request schema for asking questions"""
    query: str = Field(..., description="The question to ask", min_length=1, max_length=1000)
    k: Optional[int] = Field(default=5, description="Number of relevant documents to retrieve", ge=1, le=20)
    file_id: Optional[str] = Field(default=None, description="Optional specific file ID to search within")

class Citation(BaseModel):
    """Citation information for a source"""
    document_name: str = Field(..., description="Name of the source document")
    page_number: Optional[str] = Field(None, description="Page number if available")
    section: Optional[str] = Field(None, description="Section or chunk identifier")
    relevance_score: float = Field(..., description="Similarity/relevance score")

class QuestionResponse(BaseModel):
    """Response schema for question answers"""
    answer: str = Field(..., description="The generated answer")
    query: str = Field(..., description="The original query")
    sources: List[str] = Field(..., description="List of source document names")
    citations: List[str] = Field(..., description="List of formatted citations")
    retrieved_documents: int = Field(..., description="Number of documents retrieved")
    context_used: int = Field(..., description="Number of words used as context")
    timestamp: str = Field(..., description="Timestamp of the response")

# Streaming response schemas
class StreamingMetadata(BaseModel):
    """Metadata for streaming response"""
    sources: List[str] = Field(..., description="List of source document names")
    citations: List[str] = Field(..., description="List of formatted citations")
    retrieved_documents: int = Field(..., description="Number of documents retrieved")
    context_used: int = Field(..., description="Number of words used as context")
    query: str = Field(..., description="The original query")

class StreamingToken(BaseModel):
    """Individual token in streaming response"""
    token: str = Field(..., description="The generated token")
    partial_response: str = Field(..., description="Partial response up to this token")

class StreamingStatus(BaseModel):
    """Status update during streaming"""
    stage: str = Field(..., description="Current processing stage")
    message: str = Field(..., description="Status message")

class StreamingComplete(BaseModel):
    """Completion signal for streaming response"""
    final_response: str = Field(..., description="The complete generated response")
    timestamp: str = Field(..., description="Timestamp of completion")

class StreamingError(BaseModel):
    """Error in streaming response"""
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="User-friendly error message")

class StreamingChunk(BaseModel):
    """A single chunk in the streaming response"""
    type: Literal["metadata", "token", "status", "complete", "error"] = Field(..., description="Type of streaming chunk")
    data: Union[StreamingMetadata, StreamingToken, StreamingStatus, StreamingComplete, StreamingError] = Field(..., description="Chunk data")

class DocumentSummaryRequest(BaseModel):
    """Request schema for document summary"""
    file_id: str = Field(..., description="ID of the file to summarize")

class DocumentSummaryResponse(BaseModel):
    """Response schema for document summary"""
    summary: str = Field(..., description="Generated summary of the document")
    document_sources: List[str] = Field(..., description="Source documents used")
    sections_analyzed: int = Field(..., description="Number of document sections analyzed")
    file_id: str = Field(..., description="ID of the summarized file")

class SearchRequest(BaseModel):
    """Request schema for semantic search"""
    query: str = Field(..., description="Search query", min_length=1, max_length=500)
    k: Optional[int] = Field(default=10, description="Number of results to return", ge=1, le=50)
    file_id: Optional[str] = Field(default=None, description="Optional specific file ID to search within")
    min_similarity: Optional[float] = Field(default=0.0, description="Minimum similarity threshold", ge=0.0, le=1.0)

class SearchResult(BaseModel):
    """Individual search result"""
    content: str = Field(..., description="Content of the document chunk")
    citation: str = Field(..., description="Formatted citation")
    similarity_score: float = Field(..., description="Similarity score")
    metadata: Dict[str, Any] = Field(..., description="Additional metadata")
    rank: int = Field(..., description="Rank in search results")

class SearchResponse(BaseModel):
    """Response schema for search results"""
    results: List[SearchResult] = Field(..., description="List of search results")
    query: str = Field(..., description="The original search query")
    total_results: int = Field(..., description="Total number of results found")
    search_time: str = Field(..., description="Time taken for search")

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import json
import asyncio

from src.schemas.question_and_answer import (
    QuestionRequest, QuestionResponse,
    DocumentSummaryRequest, DocumentSummaryResponse,
    SearchRequest, SearchResponse
)
from src.services.retriever import rag_retriever
from src.utils.logger import stage_logger, ProcessingStage

router = APIRouter(prefix="/qa", tags=["Question & Answer"])

@router.post("/ask")
async def ask_question(request: QuestionRequest):
    """
    Ask a question and get a streaming AI-generated answer based on uploaded documents
    
    This endpoint:
    1. Takes a user query and embeds it
    2. Finds relevant document chunks using vector similarity
    3. Uses GPT-4o to generate a comprehensive answer with real-time streaming
    4. Returns the answer with proper citations and metadata via Server-Sent Events
    
    Response format: Server-Sent Events (SSE) with JSON chunks
    """
    
    async def generate_stream():
        """Generator function for streaming response"""
        try:
            stage_logger.info(ProcessingStage.INDEXING, f"Received streaming question: {request.query[:100]}...")
            
            # Process the question using streaming RAG
            async for chunk in rag_retriever.ask_question_streaming(
                query=request.query,
                k=request.k,
                file_id=request.file_id
            ):
                # Format as Server-Sent Events
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
            
            # Send final event to signal completion
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Streaming question processing failed: {str(e)}")
            error_chunk = {
                "type": "error",
                "data": {
                    "error": str(e),
                    "message": "Failed to process streaming question"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.post("/search", response_model=SearchResponse)
async def semantic_search(request: SearchRequest) -> SearchResponse:
    """
    Perform semantic search across uploaded documents
    
    Returns relevant document chunks without generating an AI response.
    Useful for finding specific information or exploring document content.
    """
    try:
        stage_logger.info(ProcessingStage.INDEXING, f"Semantic search: {request.query[:100]}...")
        
        # Embed the search query
        query_embedding = await rag_retriever.embed_query(request.query)
        
        # Retrieve relevant documents
        retrieved_docs = await rag_retriever.retrieve_relevant_documents(
            query_embedding=query_embedding,
            k=request.k,
            file_id=request.file_id
        )
        
        # Filter by minimum similarity if specified
        if request.min_similarity > 0:
            retrieved_docs = [
                doc for doc in retrieved_docs 
                if doc["similarity_score"] >= request.min_similarity
            ]
        
        # Format results
        search_results = []
        for doc in retrieved_docs:
            search_results.append({
                "content": doc["content"],
                "citation": doc["citation"],
                "similarity_score": doc["similarity_score"],
                "metadata": doc["metadata"],
                "rank": doc["rank"]
            })
        
        return SearchResponse(
            results=search_results,
            query=request.query,
            total_results=len(search_results),
            search_time=stage_logger._get_timestamp()
        )
        
    except Exception as e:
        stage_logger.error(ProcessingStage.INDEXING, f"Semantic search failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

@router.post("/summarize", response_model=DocumentSummaryResponse)
async def summarize_document(request: DocumentSummaryRequest) -> DocumentSummaryResponse:
    """
    Generate a comprehensive summary of a specific document
    
    Uses RAG to analyze the document and provide a structured summary
    including main topics, key points, and document structure.
    """
    try:
        stage_logger.info(ProcessingStage.INDEXING, f"Generating summary for file: {request.file_id}")
        
        # Generate document summary
        result = await rag_retriever.get_document_summary(request.file_id)
        
        return DocumentSummaryResponse(
            **result,
            file_id=request.file_id
        )
        
    except Exception as e:
        stage_logger.error(ProcessingStage.INDEXING, f"Document summarization failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )

@router.get("/status")
async def qa_status():
    """Get the status of the Q&A system"""
    try:
        # Check if models are initialized
        models_status = {
            "embedding_model": rag_retriever.embeddings_model is not None,
            "llm_model": rag_retriever.llm is not None,
            "streaming_llm": rag_retriever.streaming_llm is not None,
            "embedding_model_name": getattr(rag_retriever.embeddings_model, 'model_name', None),
            "llm_model_name": "gpt-4o" if rag_retriever.llm else None,
            "streaming_enabled": True
        }
        
        # Get vector store info
        collection_info = rag_retriever.vector_store.get_collection_info()
        
        return {
            "status": "operational",
            "models": models_status,
            "vector_store": collection_info,
            "capabilities": [
                "Question Answering with Citations",
                "Real-time Streaming Responses (SSE)",
                "Semantic Document Search", 
                "Document Summarization",
                "Multi-document RAG"
            ]
        }
        
    except Exception as e:
        stage_logger.error(ProcessingStage.INDEXING, f"Status check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "models": {"initialized": False}
        }

@router.get("/health")
async def health_check():
    """Health check for Q&A system"""
    try:
        # Simple test query to verify system is working
        test_result = await rag_retriever.embed_query("test")
        
        return {
            "status": "healthy",
            "embedding_dimension": len(test_result) if test_result else 0,
            "streaming_available": rag_retriever.streaming_llm is not None,
            "timestamp": stage_logger._get_timestamp()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Q&A system unhealthy: {str(e)}"
        )

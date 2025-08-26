import asyncio
import os
import json
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain.schema import Document
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager

from config import settings
from src.services.storage import chroma_service
from src.utils.logger import stage_logger, ProcessingStage

class StreamingCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for streaming LLM responses"""
    
    def __init__(self):
        self.tokens = []
        self.is_streaming = True
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called when a new token is generated"""
        if self.is_streaming:
            self.tokens.append(token)

class RAGRetriever:
    """RAG (Retrieval-Augmented Generation) service for document Q&A"""
    
    def __init__(self):
        self.vector_store = chroma_service
        self.embeddings_model = None
        self.llm = None
        self.streaming_llm = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize embedding model and LLM"""
        try:
            # Initialize embedding model (same as used in ingestion)
            self.embeddings_model = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={'device': settings.EMBEDDING_DEVICE},
                encode_kwargs={'normalize_embeddings': settings.NORMALIZE_EMBEDDINGS}
            )
            
            # Initialize GPT-4o model for regular responses
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,  # Low temperature for more consistent responses
                max_tokens=2000,
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
            
            # Initialize streaming GPT-4o model
            self.streaming_llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,
                max_tokens=2000,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                streaming=True  # Enable streaming
            )
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"RAG models initialized: {settings.EMBEDDING_MODEL} + GPT-4o (streaming enabled)")
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Failed to initialize models: {str(e)}")
            raise Exception(f"Model initialization failed: {str(e)}")
    
    async def embed_query(self, query: str) -> List[float]:
        """Generate embedding for user query"""
        try:
            # Run embedding in executor to avoid blocking
            embedding = await asyncio.get_event_loop().run_in_executor(
                None,
                self.embeddings_model.embed_query,
                query
            )
            return embedding
            
        except Exception as e:
            stage_logger.error(ProcessingStage.EMBEDDING, f"Query embedding failed: {str(e)}")
            raise Exception(f"Failed to embed query: {str(e)}")
    
    async def retrieve_relevant_documents(self, query_embedding: List[float], 
                                        k: int = 5, file_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant documents with metadata and citations"""
        try:
            # Search for similar documents in ChromaDB
            search_results = await self.vector_store.search_similar_documents(
                query_embedding=query_embedding,
                n_results=k,
                file_id=file_id
            )
            
            # Format results with citations
            retrieved_docs = []
            for i, (doc_text, metadata, distance) in enumerate(zip(
                search_results["documents"],
                search_results["metadatas"], 
                search_results["distances"]
            )):
                doc_info = {
                    "content": doc_text,
                    "metadata": metadata,
                    "similarity_score": 1 - distance,  # Convert distance to similarity
                    "rank": i + 1,
                    "citation": self._create_citation(metadata)
                }
                retrieved_docs.append(doc_info)
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Retrieved {len(retrieved_docs)} relevant documents")
            
            return retrieved_docs
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Document retrieval failed: {str(e)}")
            raise Exception(f"Failed to retrieve documents: {str(e)}")
    
    def _create_citation(self, metadata: Dict[str, Any]) -> str:
        """Create citation string from document metadata"""
        doc_name = metadata.get('doc_name', 'Unknown Document')
        page_num = metadata.get('page_number', metadata.get('page', 'N/A'))
        chunk_id = metadata.get('chunk_index', metadata.get('chunk_id', ''))
        
        # Create formatted citation
        citation = f"{doc_name}"
        if page_num != 'N/A':
            citation += f", Page {page_num}"
        if chunk_id:
            citation += f", Section {chunk_id}"
            
        return citation
    
    def _format_context(self, retrieved_docs: List[Dict[str, Any]]) -> str:
        """Format retrieved documents as context for the LLM"""
        context_parts = []
        
        for doc in retrieved_docs:
            context_part = f"""
Source: {doc['citation']}
Content: {doc['content']}
Relevance Score: {doc['similarity_score']:.3f}
---"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _create_rag_prompt(self) -> ChatPromptTemplate:
        """Create the RAG prompt template"""
        system_message = """You are a helpful AI assistant that answers questions based on the provided document context. 

Instructions:
1. Use ONLY the information provided in the context to answer questions
2. If the context doesn't contain enough information to answer the question, say so clearly
3. Always cite your sources using the provided source information
4. Be precise and accurate in your responses
5. If multiple sources support your answer, mention all relevant sources
6. Maintain a professional and helpful tone

Context format: Each piece of context includes a Source citation and Content.
"""
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_message),
            HumanMessage(content="""
Context:
{context}

Question: {question}

Please provide a comprehensive answer based on the context above, including proper citations.
""")
        ])
        
        return prompt
    
    async def generate_response(self, query: str, context: str, retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate response using LLM with retrieved context"""
        try:
            # Create RAG chain
            prompt = self._create_rag_prompt()
            
            # Create the chain
            chain = (
                {
                    "context": lambda x: context,
                    "question": lambda x: query
                }
                | prompt 
                | self.llm 
                | StrOutputParser()
            )
            
            # Generate response
            response = await chain.ainvoke({"query": query})
            
            # Prepare metadata with citations
            citations = [doc["citation"] for doc in retrieved_docs]
            sources = list(set([doc["metadata"].get("doc_name", "Unknown") for doc in retrieved_docs]))
            
            result = {
                "answer": response,
                "sources": sources,
                "citations": citations,
                "retrieved_documents": len(retrieved_docs),
                "context_used": len(context.split())
            }
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Generated response using {len(retrieved_docs)} documents")
            
            return result
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Response generation failed: {str(e)}")
            raise Exception(f"Failed to generate response: {str(e)}")
    
    async def generate_streaming_response(self, query: str, context: str, retrieved_docs: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response using LLM with retrieved context"""
        try:
            # Create RAG prompt
            prompt = self._create_rag_prompt()
            
            # Prepare metadata with citations
            citations = [doc["citation"] for doc in retrieved_docs]
            sources = list(set([doc["metadata"].get("doc_name", "Unknown") for doc in retrieved_docs]))
            
            # Send initial metadata
            yield {
                "type": "metadata",
                "data": {
                    "sources": sources,
                    "citations": citations,
                    "retrieved_documents": len(retrieved_docs),
                    "context_used": len(context.split()),
                    "query": query
                }
            }
            
            # Create the streaming chain
            chain = (
                {
                    "context": lambda x: context,
                    "question": lambda x: query
                }
                | prompt 
                | self.streaming_llm
            )
            
            # Stream the response
            full_response = ""
            async for chunk in chain.astream({"query": query}):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    full_response += token
                    yield {
                        "type": "token",
                        "data": {
                            "token": token,
                            "partial_response": full_response
                        }
                    }
            
            # Send completion signal
            yield {
                "type": "complete",
                "data": {
                    "final_response": full_response,
                    "timestamp": stage_logger._get_timestamp()
                }
            }
            
            stage_logger.info(ProcessingStage.INDEXING, 
                            f"Generated streaming response using {len(retrieved_docs)} documents")
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Streaming response generation failed: {str(e)}")
            yield {
                "type": "error",
                "data": {
                    "error": str(e),
                    "message": "Failed to generate streaming response"
                }
            }
    
    async def ask_question(self, query: str, k: int = 5, file_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main RAG function that processes user query and returns answer with citations
        
        Args:
            query: User's question
            k: Number of relevant documents to retrieve (default: 5)
            file_id: Optional specific file ID to search within
        
        Returns:
            Dict containing answer, sources, citations, and metadata
        """
        try:
            with stage_logger.time_stage(ProcessingStage.INDEXING, f"rag_query"):
                # Step 1: Embed the user query
                stage_logger.info(ProcessingStage.EMBEDDING, f"Processing query: {query[:100]}...")
                query_embedding = await self.embed_query(query)
                
                # Step 2: Retrieve relevant documents
                retrieved_docs = await self.retrieve_relevant_documents(
                    query_embedding=query_embedding,
                    k=k,
                    file_id=file_id
                )
                
                if not retrieved_docs:
                    return {
                        "answer": "I couldn't find any relevant documents to answer your question. Please make sure documents have been uploaded and indexed.",
                        "sources": [],
                        "citations": [],
                        "retrieved_documents": 0,
                        "context_used": 0
                    }
                
                # Step 3: Format context for LLM
                context = self._format_context(retrieved_docs)
                
                # Step 4: Generate response using LLM
                response = await self.generate_response(query, context, retrieved_docs)
                
                # Add query metadata
                response["query"] = query
                response["timestamp"] = stage_logger._get_timestamp()
                
                return response
                
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"RAG query failed: {str(e)}")
            raise Exception(f"Failed to process question: {str(e)}")
    
    async def ask_question_streaming(self, query: str, k: int = 5, file_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming version of ask_question that yields response chunks in real-time
        
        Args:
            query: User's question
            k: Number of relevant documents to retrieve (default: 5)
            file_id: Optional specific file ID to search within
        
        Yields:
            Dict containing streaming response chunks
        """
        try:
            with stage_logger.time_stage(ProcessingStage.INDEXING, f"rag_streaming_query"):
                # Step 1: Send processing status
                yield {
                    "type": "status",
                    "data": {
                        "stage": "embedding",
                        "message": "Processing your query..."
                    }
                }
                
                # Step 2: Embed the user query
                stage_logger.info(ProcessingStage.EMBEDDING, f"Processing streaming query: {query[:100]}...")
                query_embedding = await self.embed_query(query)
                
                # Step 3: Send retrieval status
                yield {
                    "type": "status",
                    "data": {
                        "stage": "retrieval",
                        "message": "Finding relevant documents..."
                    }
                }
                
                # Step 4: Retrieve relevant documents
                retrieved_docs = await self.retrieve_relevant_documents(
                    query_embedding=query_embedding,
                    k=k,
                    file_id=file_id
                )
                
                if not retrieved_docs:
                    yield {
                        "type": "error",
                        "data": {
                            "message": "I couldn't find any relevant documents to answer your question. Please make sure documents have been uploaded and indexed.",
                            "sources": [],
                            "citations": []
                        }
                    }
                    return
                
                # Step 5: Format context for LLM
                context = self._format_context(retrieved_docs)
                
                # Step 6: Send generation status
                yield {
                    "type": "status",
                    "data": {
                        "stage": "generation",
                        "message": "Generating response..."
                    }
                }
                
                # Step 7: Generate streaming response
                async for chunk in self.generate_streaming_response(query, context, retrieved_docs):
                    yield chunk
                
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Streaming RAG query failed: {str(e)}")
            yield {
                "type": "error",
                "data": {
                    "error": str(e),
                    "message": "Failed to process streaming question"
                }
            }
    
    async def get_document_summary(self, file_id: str) -> Dict[str, Any]:
        """Get a summary of a specific document using RAG"""
        summary_query = "Please provide a comprehensive summary of this document, including its main topics, key points, and structure."
        
        try:
            result = await self.ask_question(
                query=summary_query,
                k=10,  # Get more chunks for better summary
                file_id=file_id
            )
            
            return {
                "summary": result["answer"],
                "document_sources": result["sources"],
                "sections_analyzed": result["retrieved_documents"]
            }
            
        except Exception as e:
            stage_logger.error(ProcessingStage.INDEXING, f"Document summary failed: {str(e)}")
            raise Exception(f"Failed to generate document summary: {str(e)}")

# Global RAG retriever instance
rag_retriever = RAGRetriever()

from fastapi import APIRouter, HTTPException
from src.services.retriever import retrieve_and_generate
from src.schemas.question_and_answer import QuestionRequest, QuestionResponse

router = APIRouter()

@router.post("/ask", response_model=QuestionResponse, summary="Ask a question using RAG model")
async def ask_question(question_request: QuestionRequest):
    """
    Endpoint to ask a question and get an answer using the RAG model.
    """
    try:
        response = await retrieve_and_generate(question_request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

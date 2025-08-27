from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from src.services.retriever import retrieve_and_generate
from src.schemas.question_and_answer import QuestionRequest, QuestionResponse

router = APIRouter()

@router.post("/ask", summary="Ask a question using RAG model")
async def ask_question(question_request: QuestionRequest):
    """
    Endpoint to ask a question and get an answer using the RAG model.
    """
    async def event_generator():
        try:
            response = await retrieve_and_generate(question_request)
            yield {
                "event": "message",
                "data": response.json()
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": str(e)
            }

    return EventSourceResponse(event_generator())

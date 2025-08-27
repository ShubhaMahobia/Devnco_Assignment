from src.services.ingestion import DocumentProcessor
from src.services.storage import chroma_service
from src.schemas.question_and_answer import QuestionRequest, QuestionResponse
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage
from langchain_core.documents import Document

async def retrieve_and_generate(question_request: QuestionRequest) -> QuestionResponse:
    """
    Full RAG function to process a user query, fetch relevant data, and generate a response using LLM.
    """
    # Initialize document processor
    document_processor = DocumentProcessor()

    # Step 1: Embed the user query
    query_document = Document(page_content=question_request.query)
    query_embedding = await document_processor.generate_embeddings([query_document])

    # Step 2: Fetch relevant data from vector storage
    search_results = await chroma_service.search_similar_documents(query_embedding[0], n_results=question_request.k)
    relevant_docs = [Document(page_content=doc, metadata=meta) for doc, meta in zip(search_results['documents'], search_results['metadatas'])]

    # Step 3: Create context with fetched documents and query
    context = question_request.query + "\n" + "\n".join([doc.page_content for doc in relevant_docs])

    # Step 4: Pass context to LLM (GPT-4o mini)
    response_text = await generate_response(context)

    # Step 5: Return the result
    return QuestionResponse(
        answer=response_text,
        query=question_request.query,
        sources=[doc.metadata.get('source', 'Unknown source') for doc in relevant_docs],
        citations=[doc.metadata.get('citation', 'No citation available') for doc in relevant_docs],
        retrieved_documents=len(relevant_docs),
        context_used=len(context.split()),
        timestamp=datetime.now().isoformat()
    )


# RAG function using LangChain to generate a response with relevant context
async def generate_response(context: str) -> str:
    """
    Uses LangChain to generate a response from an LLM given the provided context.
    """
    # Define a prompt template for the LLM
    prompt_template = (
        "You are a helpful assistant application.\n"
        "Given the following context, answer the user's question as accurately and concisely as possible.\n\n"
        "Context:\n{context}\n\n"
        "Instructions:\n"
        "- Base your answer only on the provided context.\n"
        "- If the answer is not found in the context, say \"I could not find the answer in the provided information.\"\n"
        "- Cite sources or document titles if available.\n\n"
        "Answer:"
    )
    prompt = ChatPromptTemplate.from_template(prompt_template)
    formatted_prompt = prompt.format(context=context)

    # Initialize the LLM (ensure your OpenAI API key is set in the environment)
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

    # Generate the response
    response = await llm.agenerate([[HumanMessage(content=formatted_prompt)]])
    return response.generations[0][0].text.strip()

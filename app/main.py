# ============================================================
# NEXUS-RAG: Anuj's Enterprise eXplainable Unified Search & RAG
# CRITICAL: logfire MUST be configured before ALL other imports
# so that spans from all modules are captured from the start.
# ============================================================
import os
import logfire
from dotenv import load_dotenv

load_dotenv()
if os.getenv("LOGFIRE_TOKEN"):
    logfire.configure(
        token=os.getenv("LOGFIRE_TOKEN"),
        service_name="nexus-rag-api"
    )

# Safe to import app modules now - logfire is already active
from fastapi import FastAPI, Response, status, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.config import settings
from app.agents.graph import rag_agent
from app.guardrails import initialize_rails, guard

# Initialize FastAPI
app = FastAPI(
    title="NEXUS-RAG: Enterprise Document Intelligence API",
    description="Agentic Document Intelligence for Reliable Enterprise Search — Built by Anuj Kekre",
    version="1.0.0"
)

@app.on_event("startup")
def startup_event():
    initialize_rails()

class QueryRequest(BaseModel):
    q: str = Field(..., description="User question or search query")
    thread_id: Optional[str] = Field("default_user", description="Session / conversation thread ID")

class QueryResponse(BaseModel):
    question: str
    answer: str
    thought_process: List[str]
    status: str
    sources: List[str]

@app.get("/")
def home():
    return {
        "project": "NEXUS-RAG",
        "title": "Anuj's Enterprise eXplainable Unified Search & RAG",
        "author": "Anuj Kekre",
        "status": "operational",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    """
    Health check endpoint reporting status of core services and configuration.
    """
    return {
        "status": "healthy",
        "service": "NEXUS-RAG API",
        "version": "1.0.0",
        "vector_collection": settings.QDRANT_COLLECTION,
        "reasoning_model": settings.GROQ_MODEL,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "observability": {
            "logfire": bool(os.getenv("LOGFIRE_TOKEN")),
            "langsmith": os.getenv("LANGSMITH_TRACING", "false") == "true"
        }
    }

@app.get("/graph")
def get_graph_image():
    """
    Returns the Mermaid image of the agent's workflow.
    """
    try:
        png_bytes = rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        return {"error": f"Could not generate graph image: {e}"}

@app.get("/collection/stats")
def collection_stats():
    """Returns knowledge base stats (points count, collection name)."""
    try:
        from app.services.retrieval.qdrant_service import get_qdrant_client
        client = get_qdrant_client()
        info = client.get_collection(settings.QDRANT_COLLECTION)
        return {
            "collection": settings.QDRANT_COLLECTION,
            "points_count": info.points_count,
            "status": "ready"
        }
    except Exception as e:
        return {
            "collection": settings.QDRANT_COLLECTION,
            "points_count": 0,
            "error": str(e)
        }

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Ingests an uploaded document directly into the Qdrant knowledge base.
    Supports: .pdf, .docx, .pptx, .txt, .html, .htm
    """
    import shutil
    import uuid
    from qdrant_client.http import models
    from app.services.retrieval.qdrant_service import get_qdrant_client
    from app.ingestion.chunking.splitter import chunk_text
    from app.services.retrieval.embedding import embed_texts

    filename = file.filename or "uploaded_file"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx", "pptx", "txt", "html", "htm"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type .{ext}. Supported types: pdf, docx, pptx, txt, html"
        )

    upload_dir = os.path.abspath("DATA/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    temp_path = os.path.join(upload_dir, f"{uuid.uuid4().hex[:8]}_{filename}")

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Parse text based on extension
        if ext == "pdf":
            from app.ingestion.loaders.pdf import parse_pdf
            full_text = parse_pdf(temp_path)
        elif ext in ("docx", "pptx"):
            from app.ingestion.loaders.office import parse_office
            full_text = parse_office(temp_path)
        elif ext in ("html", "htm"):
            from app.ingestion.loaders.html import parse_html
            full_text = parse_html(temp_path)
        elif ext == "txt":
            from app.ingestion.loaders.text import parse_text
            full_text = parse_text(temp_path)
        else:
            full_text = ""

        if not full_text or not full_text.strip():
            raise HTTPException(status_code=400, detail=f"No readable text could be extracted from {filename}.")

        # 2. Chunk text
        chunks = chunk_text(full_text)
        if not chunks:
            raise HTTPException(status_code=400, detail="Document could not be chunked.")

        # 3. Vectorize and Index into Qdrant
        embeddings = embed_texts(chunks)
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": chunk,
                    "source": filename,
                    "source_type": "user_upload",
                },
            )
            for chunk, vector in zip(chunks, embeddings)
        ]

        client = get_qdrant_client()
        client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=points,
        )

        return {
            "status": "success",
            "filename": filename,
            "chunks_indexed": len(points),
            "message": f"Successfully indexed {len(points)} chunks from '{filename}' into NEXUS-RAG."
        }

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to process uploaded file {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    Executes the NEXUS-RAG agentic flow with conversation memory.
    """
    q = request.q.strip()
    thread_id = request.thread_id or "default_user"

    if not q:
        return {
            "question": "",
            "answer": "Please provide a valid question.",
            "thought_process": ["Query empty"],
            "status": "idle",
            "sources": []
        }

    initial_state = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing NEXUS-RAG Graph..."
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Gate 1: NeMo Guardrails — blocks off-topic, jailbreaks, and handles dialog
        rail_fired, rail_response = guard(q)
        if rail_fired:
            logfire.info(f"🛡️ Request intercepted by guardrails | thread={thread_id}")
            return {
                "question": q,
                "answer": rail_response,
                "thought_process": [
                    "Safety guardrails evaluated",
                    "Policy triggered: Intercepted before retrieval"
                ],
                "status": "Guardrail policy triggered",
                "sources": []
            }

        # Gate 2: LangGraph RAG pipeline
        final_output = rag_agent.invoke(initial_state, config=config)
        
        return {
            "question": q,
            "answer": final_output.get("final_answer", "No answer generated."),
            "thought_process": final_output.get("plan", ["Response generated"]),
            "status": final_output.get("status", "Complete"),
            "sources": final_output.get("documents", [])
        }
    except Exception as e:
        logfire.error(f"❌ NEXUS-RAG Backend Execution Failed: {e}")
        return {
            "question": q,
            "answer": "I encountered an internal error while processing your request. Please try again.",
            "thought_process": ["Error encountered during execution"],
            "status": "error",
            "sources": []
        }


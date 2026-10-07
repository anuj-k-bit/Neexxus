import logfire
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings
from app.services.retrieval.embedding import embed_query

_qdrant_client = None

def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        if settings.QDRANT_URL:
            _qdrant_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY
            )
        else:
            _qdrant_client = QdrantClient(path="./qdrant_local")
    return _qdrant_client

def search_enterprise_knowledge(query: str, limit: int = 8):
    """
    Performs high-precision vector search in the NEXUS-RAG knowledge base.
    Uses the modern query_points interface with payload hydration.
    """
    try:
        query_vector = embed_query(query)
        client = get_qdrant_client()

        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=limit,
            with_payload=True
        )

        results = []
        for res in response.points:
            payload = res.payload or {}
            results.append({
                "content": payload.get("text", ""),
                "source": payload.get("source", "Enterprise Knowledge Base"),
                "score": res.score
            })
        
        return results
    except Exception as e:
        print(f"❌ Vector search error: {e}", flush=True)
        logfire.error(f"❌ NEXUS-RAG Vector Search Failed: {e}")
        return []


import logfire
from app.agents.state import AgentState
from app.services.retrieval.qdrant_service import search_enterprise_knowledge
from app.services.retrieval.ranking_service import rerank_documents

def retrieve_node(state: AgentState):
    """
    Performs vector search and semantic reranking for technical queries in NEXUS-RAG.
    """
    query = state.get("current_query", "")
    
    with logfire.span("🔍 NEXUS-RAG Retrieval"):
        logfire.info(f"Querying Qdrant knowledge base for: {query}")
        raw_results = search_enterprise_knowledge(query, limit=15)
        count_retrieved = len(raw_results)
        logfire.info(f"Retrieved {count_retrieved} candidates from Vector DB")
        
        if not raw_results:
            logfire.warning("No candidate documents found in vector store.")
            return {
                "documents": [],
                "status": "No relevant documents found in knowledge base.",
                "plan": state.get("plan", []) + [
                    "Documents retrieved: 0 candidates found",
                    "Results reranked: Skipped (empty candidate pool)"
                ]
            }
        
        doc_contents = [doc['content'] for doc in raw_results]
        
        with logfire.span("⚖️ FlashRank Semantic Reranking"):
            reranked_contents = rerank_documents(query, doc_contents, top_n=5)
            count_reranked = len(reranked_contents)
            logfire.info(f"Reranking complete. Selected top {count_reranked} chunks.")
            
        formatted_docs = []
        for i, doc_text in enumerate(reranked_contents):
            # Match back source if available
            source_file = "Enterprise Documentation"
            for raw in raw_results:
                if raw.get("content") == doc_text:
                    source_file = raw.get("source", "Enterprise Documentation")
                    break
            formatted_docs.append(f"[Source: {source_file}]\n{doc_text}")
    
    return {
        "documents": formatted_docs,
        "status": f"Retrieved and reranked {count_reranked} relevant context chunks.",
        "plan": state.get("plan", []) + [
            f"Documents retrieved: {count_retrieved} vector candidates",
            f"Results reranked: Top {count_reranked} semantic matches selected"
        ]
    }


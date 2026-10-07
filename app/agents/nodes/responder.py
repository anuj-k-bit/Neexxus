import logfire
from app.agents.state import AgentState
from app.config import settings
from app.gateway.client import portkey_client, extract_cache_status, USE_PORTKEY

def generate_node(state: AgentState):
    """
    Synthesizes grounded responses in NEXUS-RAG using documentation context and conversational memory.
    Surfaces gateway cache status (Hit/Miss) for observability.
    """
    query = state.get("current_query", "")
    documents = state.get("documents", [])

    history_str = ""
    for msg in state.get("messages", [])[:-1]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_str += f"{role}: {msg.get('content', '')}\n"

    user_msg = state["messages"][-1]["content"] if state.get("messages") else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")
        prompt = f"""
        You are NEXUS-RAG, an intelligent Enterprise AI Assistant developed by Anuj Kekre.
        Answer the user's latest message politely and concisely using the CONVERSATION HISTORY below.

        CONVERSATION HISTORY:
        {history_str if history_str.strip() else "(No prior messages)"}

        LATEST USER MESSAGE:
        "{user_msg}"
        """
    elif not documents:
        logfire.info("No documents retrieved — generating transparent empty-result response.")
        prompt = f"""
        You are NEXUS-RAG, an enterprise search and document intelligence system.
        The user asked a technical question, but no relevant documentation was found in the indexed enterprise knowledge base.

        USER QUESTION:
        "{user_msg}"

        Task:
        Politely explain that no matching documents were found in the current knowledge repository.
        Suggest the user clarify the query, verify indexing status, or provide additional document context.
        Do not make up facts or pretend you have the internal document.
        """
    else:
        logfire.info(f"Generating technical RAG response from {len(documents)} retrieved chunks.")
        max_context_chars = 10000
        full_context = ""

        for doc in documents:
            if len(full_context) + len(doc) < max_context_chars:
                full_context += doc + "\n\n---\n\n"
            else:
                logfire.warning("Context truncated to fit model token limits.")
                break

        prompt = f"""
        You are NEXUS-RAG, an Enterprise Explainable Unified Search & Document Intelligence assistant.
        Answer the user question accurately using ONLY the TECHNICAL CONTEXT provided below.

        GUIDELINES:
        1. Ground your answer strictly in the provided context.
        2. Reference source filenames when stating facts (e.g., "[Source: filename]").
        3. If the context does not fully answer the question, acknowledge the gap honestly.
        4. Be structured, professional, and clear.

        TECHNICAL CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str if history_str.strip() else "(No prior messages)"}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ NEXUS-RAG LLM Synthesis"):
        try:
            model_name = f"@{settings.GROQ_SLUG}/{settings.GROQ_MODEL}" if USE_PORTKEY else settings.GROQ_MODEL
            response = portkey_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0.1
            )
            content = response.choices[0].message.content
            cache_status = extract_cache_status(response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:
                logfire.info("⚡ Gateway Cache Hit — response served from Portkey cache.")
                plan_update = state.get("plan", []) + ["Response generated: Portkey Gateway Cache Hit (0ms) ⚡"]
                status_msg = "Response served from gateway cache."
            else:
                logfire.info("✅ Response synthesized via Groq LLM.")
                plan_update = state.get("plan", []) + ["Response generated: LLM synthesis complete"]
                status_msg = "Response generated successfully."

            return {
                "final_answer": content,
                "status": status_msg,
                "plan": plan_update,
                "messages": [{"role": "assistant", "content": content}]
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed: {e}")
            raise e


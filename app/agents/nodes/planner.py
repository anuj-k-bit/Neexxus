from app.agents.state import AgentState
from app.gateway import get_langchain_llm
import logfire

# Portkey-backed LLM: fallback + cache + retry
llm = get_langchain_llm(feature="planner")

def planner_node(state: AgentState):
    """
    The Planner determines if knowledge retrieval is needed based on conversation context.
    """
    history = ""
    for msg in state.get("messages", [])[:-1]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        history += f"{role}: {msg.get('content', '')}\n"
    
    user_message = state["messages"][-1]["content"] if state.get("messages") else ""
    
    prompt = f"""
    You are the Query Planner for NEXUS-RAG, an enterprise document intelligence assistant.
    Analyze the conversation history and the latest user message.
    
    CONVERSATION HISTORY:
    {history if history.strip() else "(No prior conversation)"}
    
    LATEST MESSAGE:
    "{user_message}"
    
    Task:
    1. If the latest message is a greeting, farewell, or can be answered strictly from the conversation history above, output: CONVERSATIONAL
    2. If the user asks a technical or factual question requiring documentation lookup, output an optimized search query.
    
    Output ONLY 'CONVERSATIONAL' or the optimized search query. Do not include quotes or preamble.
    """
    
    with logfire.span("🧠 NEXUS-RAG Planner"):
        try:
            decision = llm.invoke(prompt).content.strip()
            # Sanitize output
            decision = decision.replace('"', '').replace("'", "").strip()
            logfire.info(f"Planner classified query intent: {decision}")
        except Exception as e:
            logfire.error(f"Planner execution failed: {e}. Defaulting to user message query.")
            decision = user_message
    
    if decision == "CONVERSATIONAL":
        return {
            "current_query": "CONVERSATIONAL",
            "status": "Conversational query — retrieving from conversation memory.",
            "plan": [
                "Query classified: Conversational context",
                "Knowledge retrieval: Skipped (direct memory response)"
            ]
        }
    
    return {
        "current_query": decision,
        "status": f"Technical query identified — searching enterprise knowledge base.",
        "plan": [
            "Query classified: Technical retrieval",
            f"Retrieval started: '{decision}'"
        ]
    }


import os
import sys
import streamlit as st
import requests
import time
import uuid
import logfire
from dotenv import load_dotenv

# Ensure root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load environment variables from .env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)

# Synchronize Streamlit Cloud Secrets into environment variables
try:
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

# Initialize Logfire
try:
    token = os.getenv("LOGFIRE_TOKEN")
    if token:
        logfire.configure(token=token, service_name="nexus-rag-ui")
        LOGFIRE_STATUS = "Active & Tracing"
    else:
        LOGFIRE_STATUS = "Standby (No Token)"
except Exception as e:
    LOGFIRE_STATUS = f"Standby ({e})"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="NEXUS-RAG — Agentic Document Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS STYLING ---
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background: linear-gradient(180deg, #0e1117 0%, #161b22 100%);
    }
    
    /* Header container */
    .nexus-header {
        padding: 1.5rem 1.5rem;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(148, 163, 184, 0.15);
        backdrop-filter: blur(10px);
        margin-bottom: 1.5rem;
    }
    
    .nexus-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .nexus-tagline {
        font-size: 1.05rem;
        color: #94a3b8;
        font-weight: 400;
    }

    .nexus-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-right: 0.5rem;
        background-color: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }
    
    /* Status indicators */
    .step-box {
        padding: 0.5rem 0.8rem;
        margin: 0.3rem 0;
        border-radius: 8px;
        background: rgba(30, 41, 59, 0.5);
        border-left: 3px solid #38bdf8;
        font-size: 0.85rem;
        color: #e2e8f0;
    }

    /* Citation chip */
    .source-chip {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        font-size: 0.8rem;
        margin-bottom: 0.4rem;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
</style>
""", unsafe_allow_html=True)

AI_AVATAR = "⚡"
USER_AVATAR = "👤"

# --- SESSION MANAGEMENT ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info(f"✨ New User Session Initialized: {st.session_state.session_id}")

if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    backend_url = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8080"))
except Exception:
    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8080")

# --- BACKEND HEALTH PROBE ---
def check_backend_health():
    try:
        r = requests.get(f"{backend_url}/health", timeout=2)
        if r.status_code == 200:
            return True, r.json()
        return False, None
    except Exception:
        return False, None

is_backend_online, health_data = check_backend_health()

def execute_upload(file_name: str, file_bytes: bytes, file_type: str = None):
    """Handles document upload via HTTP backend if online, or in-process standalone on Streamlit Cloud."""
    if is_backend_online:
        try:
            files = {"file": (file_name, file_bytes, file_type or "application/octet-stream")}
            res = requests.post(f"{backend_url}/upload", files=files, timeout=120)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass

    # In-process standalone execution (Streamlit Cloud)
    import uuid
    from qdrant_client.http import models
    from app.config import settings
    from app.services.retrieval.qdrant_service import get_qdrant_client
    from app.ingestion.chunking.splitter import chunk_text
    from app.services.retrieval.embedding import embed_texts

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    upload_dir = os.path.abspath("DATA/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    temp_path = os.path.join(upload_dir, f"{uuid.uuid4().hex[:8]}_{file_name}")
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

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
        raise Exception(f"Unsupported file type .{ext}")

    if not full_text or not full_text.strip():
        raise Exception(f"No readable text could be extracted from {file_name}.")

    chunks = chunk_text(full_text)
    if not chunks:
        raise Exception("Document could not be chunked.")

    embeddings = embed_texts(chunks)
    points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"text": chunk, "source": file_name, "source_type": "user_upload"}
        )
        for chunk, vector in zip(chunks, embeddings)
    ]
    client = get_qdrant_client()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        from app.services.retrieval.embedding import get_embedding_dim
        dim = get_embedding_dim()
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE)
        )
    client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    return {
        "status": "success",
        "filename": file_name,
        "chunks_indexed": len(points),
        "message": f"Successfully indexed {len(points)} chunks from '{file_name}' into NEXUS-RAG."
    }

def execute_query(prompt_text: str, session_id: str):
    """Executes query via HTTP backend if online, or in-process standalone on Streamlit Cloud."""
    if is_backend_online:
        try:
            url = f"{backend_url}/query"
            payload = {"q": prompt_text, "thread_id": session_id}
            response = requests.post(url, json=payload, timeout=90)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass

    # In-process standalone execution (Streamlit Cloud)
    from app.guardrails import guard, initialize_rails
    initialize_rails()
    rail_fired, rail_response = guard(prompt_text)
    if rail_fired:
        return {
            "question": prompt_text,
            "answer": rail_response,
            "thought_process": [
                "Safety guardrails evaluated",
                "Policy triggered: Intercepted before retrieval"
            ],
            "status": "Guardrail policy triggered",
            "sources": []
        }

    from app.agents.graph import rag_agent
    initial_state = {
        "messages": [{"role": "user", "content": prompt_text}],
        "current_query": prompt_text,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing NEXUS-RAG Graph..."
    }
    config = {"configurable": {"thread_id": session_id}}
    final_output = rag_agent.invoke(initial_state, config=config)
    return {
        "question": prompt_text,
        "answer": final_output.get("final_answer", "No answer generated."),
        "thought_process": final_output.get("plan", ["Response generated"]),
        "status": final_output.get("status", "Complete"),
        "sources": final_output.get("documents", [])
    }

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚡ NEXUS-RAG")
    st.caption("Agentic Document Intelligence Platform")
    st.markdown("---")
    
    # System Status Card
    points_count = 0
    if is_backend_online:
        st.success("🟢 **Backend API**: Online & Connected")
        try:
            r = requests.get(f"{backend_url}/collection/stats", timeout=2)
            if r.status_code == 200:
                points_count = r.json().get("points_count", 0)
        except Exception:
            pass
        st.metric(label="📚 Knowledge Base Size", value=f"{points_count} chunks")
        with st.expander("System Specs", expanded=False):
            st.write(f"**Reasoning**: `{health_data.get('reasoning_model', 'Groq / GPT-OSS-120B')}`")
            st.write(f"**Embedding**: `{health_data.get('embedding_model', 'Gemini 3072-dim')}`")
            st.write(f"**Collection**: `{health_data.get('vector_collection', 'nexus_rag_knowledge')}`")
            st.write(f"**Reranker**: `FlashRank (Local ONNX)`")
            st.write(f"**Safety**: `NeMo Guardrails Active`")
    else:
        st.success("☁️ **Engine**: Standalone Cloud Engine")
        try:
            from app.services.retrieval.qdrant_service import get_qdrant_client
            from app.config import settings
            client = get_qdrant_client()
            if client.collection_exists(settings.QDRANT_COLLECTION):
                points_count = client.get_collection(settings.QDRANT_COLLECTION).points_count
        except Exception:
            pass
        st.metric(label="📚 Knowledge Base Size", value=f"{points_count} chunks")
        with st.expander("System Specs", expanded=False):
            st.write("**Reasoning**: `Groq / GPT-OSS-120B`")
            st.write("**Embedding**: `Gemini 3072-dim`")
            st.write("**Reranker**: `FlashRank (ONNX)`")
            st.write("**Mode**: `In-Process Cloud Execution`")
    
    st.markdown("---")
    st.markdown("### 📤 Ingest Documents")
    st.caption("Upload PDFs, DOCX, PPTX, or TXT directly into your vector knowledge base.")
    uploaded_files = st.file_uploader(
        "Upload files to index",
        type=["pdf", "docx", "pptx", "txt", "html"],
        accept_multiple_files=True,
        key="file_uploader"
    )
    if uploaded_files:
        if st.button("⚡ Index Documents Now", use_container_width=True, type="primary"):
            success_count = 0
            for up_file in uploaded_files:
                with st.spinner(f"Vectorizing '{up_file.name}' with Gemini..."):
                    try:
                        data = execute_upload(up_file.name, up_file.getvalue(), up_file.type)
                        st.success(f"✅ {data.get('message', 'Indexed successfully!')}")
                        success_count += 1
                    except Exception as err:
                        st.error(f"❌ Upload error: {err}")
            if success_count > 0:
                time.sleep(1.5)
                st.rerun()

    st.markdown("---")
    st.write(f"📡 **Observability**: `{LOGFIRE_STATUS}`")
    st.write(f"🔑 **Thread Memory**: `{st.session_state.session_id[:8]}...`")
    
    st.markdown("---")
    st.markdown("**Sample Enterprise Inquiries:**")
    sample_queries = [
        "How do you start Redis for a Kubernetes work queue?",
        "Explain Horizontal Pod Autoscaling (HPA) vs VPA.",
        "What are the core Kubernetes master components?",
        "How do you configure vertical pod autoscaling recommendations?"
    ]
    for sq in sample_queries:
        if st.button(f"💡 {sq[:35]}...", key=sq, use_container_width=True):
            st.session_state["preset_query"] = sq
            st.rerun()

    st.markdown("---")
    if st.session_state.messages:
        chat_transcript = f"# NEXUS-RAG Chat Transcript\nSession ID: {st.session_state.session_id}\n\n"
        for msg in st.session_state.messages:
            role = "User" if msg["role"] == "user" else "NEXUS-RAG Assistant"
            chat_transcript += f"### {role}:\n{msg['content']}\n\n---\n\n"
        st.download_button(
            label="📥 Export Chat (Markdown)",
            data=chat_transcript,
            file_name=f"nexus_rag_chat_{st.session_state.session_id[:8]}.md",
            mime="text/markdown",
            use_container_width=True
        )

    if st.button("🗑️ Reset Conversation Memory", use_container_width=True, type="secondary"):
        logfire.warning(f"Session memory cleared for: {st.session_state.session_id}")
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.markdown(
        "<div style='text-align: center; margin-top: 2rem; font-size: 0.75rem; color: #64748b;'>"
        "NEXUS-RAG v1.0.0<br>Architected by <b>Anuj Kekre</b>"
        "</div>",
        unsafe_allow_html=True
    )

# --- MAIN HEADER ---
st.markdown("""
<div class="nexus-header">
    <div class="nexus-badge">Enterprise Intelligence</div>
    <div class="nexus-badge">Multi-Stage Retrieval</div>
    <div class="nexus-badge">Safe Execution</div>
    <div class="nexus-title">NEXUS-RAG</div>
    <div class="nexus-tagline">Anuj's Enterprise eXplainable Unified Search & RAG · Agentic Document Intelligence</div>
</div>
""", unsafe_allow_html=True)

tab_chat, tab_arch = st.tabs(["💬 Enterprise Assistant", "🏗️ System Architecture & Workflow"])

with tab_chat:
    # Display chat history
    for message in st.session_state.messages:
        avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # Preset query handler
    preset = st.session_state.pop("preset_query", None)
    prompt_input = st.chat_input("Ask a technical question about your enterprise documentation...")
    active_prompt = preset or prompt_input

    if active_prompt:
        # Append user message
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(active_prompt)

        # Process assistant response
        with st.chat_message("assistant", avatar=AI_AVATAR):
            data = {}
            with st.status("⚡ NEXUS-RAG Execution Cycle...", expanded=True) as status_box:
                try:
                    with logfire.span("📡 NEXUS-RAG Query", query=active_prompt, session_id=st.session_state.session_id):
                        data = execute_query(active_prompt, st.session_state.session_id)

                    # Safe execution status display (no internal chain-of-thought exposed)
                    steps = data.get("thought_process", [])
                    for step in steps:
                        st.write(f"⚙️ {step}")

                    status_box.update(label="✅ Response Synthesized", state="complete", expanded=False)

                except Exception as e:
                    logfire.error(f"❌ Execution Error: {e}")
                    status_box.update(label="❌ Execution Error", state="error")
                    st.error(f"Internal error processing query: {e}")
                    st.stop()

            # Stream the synthesized answer
            answer_placeholder = st.empty()
            full_answer = data.get("answer", "No response generated.")
            
            curr_text = ""
            for char in full_answer:
                curr_text += char
                answer_placeholder.markdown(curr_text + "▌")
                time.sleep(0.003)
            answer_placeholder.markdown(full_answer)

            # Source Attribution / Document Inspector
            sources = data.get("sources", [])
            if sources:
                with st.expander(f"📄 Retrieved Context & Grounding Sources ({len(sources)} Chunks)", expanded=False):
                    for idx, src in enumerate(sources):
                        st.markdown(f"**Chunk {idx + 1}**")
                        st.info(src)
            else:
                st.caption("ℹ️ Response generated from conversational memory or direct synthesis.")

            st.session_state.messages.append({"role": "assistant", "content": full_answer})
            logfire.info("✅ NEXUS-RAG chat turn completed.")

with tab_arch:
    st.markdown("### 🏗️ NEXUS-RAG System Architecture & Data Flow")
    st.caption("Architected by **Anuj Kekre** · Agentic Document Intelligence Platform v1.0.0")

    st.markdown("""
    ```mermaid
    graph TD
        User([👤 User / Client]) --> UI[🖥️ Streamlit Interface Layer]
        UI -->|HTTP /query| API[⚡ FastAPI Service Gate]
        
        subgraph SafetyGate ["🛡️ Gate 1: Safety & Guardrails"]
            API --> GR{"NeMo Guardrails\\nSafety Check"}
            GR -- "Jailbreak / Toxic / Off-Topic" --> Block["🚫 Block / Intercept"]
            GR -- "Safe Query" --> Core["🧠 LangGraph Agent Core"]
        end
        
        subgraph AgentCore ["🧠 Gate 2: Agentic Planning"]
            Core --> Planner["🧭 Query Planner Node\\nIntent & Search Reformulation"]
            Planner -- "Conversational / Greeting" --> Responder["✍️ Responder Node"]
            Planner -- "Technical Question" --> Retriever["🔍 Retriever Node"]
        end
        
        subgraph RetrievalLayer ["🔎 Gate 3 & 4: Two-Stage Retrieval"]
            Retriever --> Embed["📐 Google Gemini Embedding\\n(3072-dim Cosine)"]
            Embed --> Qdrant[("🗄️ Qdrant Vector Store\\nLocal / Cloud")]
            Qdrant --> Candidates["Top 15 Vector Chunks"]
            Candidates --> FlashRank["⚖️ FlashRank Cross-Encoder\\n(ms-marco-TinyBERT ONNX)"]
            FlashRank --> Top5["Top 5 High-Precision Matches"]
        end
        
        subgraph SynthesisLayer ["✍️ Gate 5: Grounded Synthesis"]
            Top5 --> Responder
            Responder --> GroqLLM["⚡ Groq Inference Engine\\n(openai/gpt-oss-120b)"]
            GroqLLM --> Output["📑 Grounded Answer + Source Citations"]
        end
        
        Output --> UI
        Block --> UI
    ```
    """)

    st.markdown("---")
    st.markdown("#### ⚙️ Technical Component Matrix")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        | Component | Technology | Rationale |
        | :--- | :--- | :--- |
        | **User Interface** | Streamlit | Real-time telemetry, thought trace & document inspector |
        | **Backend API** | FastAPI / Uvicorn | Async performance, strict Pydantic schemas, Swagger docs |
        | **Agent Framework** | LangGraph | Stateful cyclic graph with intent routing & conversation memory |
        | **Safety Engine** | NeMo Guardrails | Deterministic Colang safety policies & jailbreak interception |
        """)
    with col2:
        st.markdown("""
        | Component | Technology | Rationale |
        | :--- | :--- | :--- |
        | **Embedding Model** | Gemini 2.0 Preview | 3072-dimensional high-resolution semantic dense vectors |
        | **Vector Database** | Qdrant (Local / Cloud) | Scalable ANN vector search with metadata payload filtering |
        | **Reranker** | FlashRank ONNX | Sub-20ms cross-encoder reranking on CPU (zero GPU needed) |
        | **LLM Engine** | Groq LPU | Sub-second token generation with `openai/gpt-oss-120b` |
        """)

    st.markdown("---")
    st.markdown("#### 🔄 The 5 Execution Gates")
    st.markdown("""
    1. **Gate 1 — NeMo Guardrails:** Validates user inputs against safety boundaries. Jailbreak attempts or off-topic abuse are stopped before hitting search or the LLM.
    2. **Gate 2 — LangGraph Planner:** Examines conversational history and reformulates technical questions into optimized dense vector search targets.
    3. **Gate 3 — Qdrant Vector Search:** Retrieves 15 semantically similar document chunks using cosine similarity across 3072 dimensions.
    4. **Gate 4 — FlashRank Reranker:** Evaluates token-level query-document cross-attention to filter out false positives and pick the top 5 chunks.
    5. **Gate 5 — Grounded Synthesis:** Feeds only verified context into Groq's high-speed inference engine, strictly enforcing source citations.
    """)


import os
import streamlit as st
import requests
import time
import uuid
import logfire
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)

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

backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")

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

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚡ NEXUS-RAG")
    st.caption("Agentic Document Intelligence Platform")
    st.markdown("---")
    
    # System Status Card
    if is_backend_online:
        st.success("🟢 **Backend API**: Online & Connected")
        points_count = 0
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
        st.error("🔴 **Backend API**: Disconnected")
        st.caption(f"Target: `{backend_url}`")
        st.info("Start API: `uvicorn app.main:app --port 8080`")
    
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
                        files = {"file": (up_file.name, up_file.getvalue(), up_file.type or "application/octet-stream")}
                        res = requests.post(f"{backend_url}/upload", files=files, timeout=120)
                        if res.status_code == 200:
                            data = res.json()
                            st.success(f"✅ {data.get('message', 'Indexed successfully!')}")
                            success_count += 1
                        else:
                            st.error(f"❌ Failed to index '{up_file.name}': {res.text}")
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
                    url = f"{backend_url}/query"
                    payload = {"q": active_prompt, "thread_id": st.session_state.session_id}
                    response = requests.post(url, json=payload, timeout=90)
                    
                    if response.status_code != 200:
                        status_box.update(label="❌ API Error", state="error")
                        st.error(f"Backend returned status {response.status_code}: {response.text}")
                        st.stop()
                        
                    data = response.json()

                # Safe execution status display (no internal chain-of-thought exposed)
                steps = data.get("thought_process", [])
                for step in steps:
                    st.write(f"⚙️ {step}")

                status_box.update(label="✅ Response Synthesized", state="complete", expanded=False)

            except requests.exceptions.ConnectionError:
                logfire.error("❌ UI cannot reach backend")
                status_box.update(label="❌ Connection Failed", state="error")
                st.error(f"Cannot connect to NEXUS-RAG backend at `{backend_url}`. Ensure `uvicorn app.main:app` is running.")
                st.stop()
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


import os
import streamlit as st
import requests
import time
import uuid
import logfire

# Initialize Logfire
try:
    token = st.secrets.get("LOGFIRE_TOKEN", os.getenv("LOGFIRE_TOKEN"))
    if token:
        logfire.configure(token=token, service_name="nexus-rag-cloud-ui")
        LOGFIRE_STATUS = "Active & Tracing"
    else:
        LOGFIRE_STATUS = "Standby (No Token)"
except Exception:
    LOGFIRE_STATUS = "Standby"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="NEXUS-RAG — Agentic Document Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .nexus-header {
        padding: 1.25rem 1.5rem;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(148, 163, 184, 0.15);
        margin-bottom: 1.5rem;
    }
    .nexus-title {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .nexus-tagline {
        font-size: 1rem;
        color: #94a3b8;
    }
</style>
""", unsafe_allow_html=True)

AI_AVATAR = "⚡"
USER_AVATAR = "👤"

# --- SESSION MANAGEMENT ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info(f"✨ New User Session Created: {st.session_state.session_id}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚡ NEXUS-RAG")
    st.caption("Anuj's Enterprise Unified Search & RAG")
    st.markdown("---")

    base_url = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000"))

    st.write(f"📡 **Observability**: `{LOGFIRE_STATUS}`")
    st.write(f"🔑 **Thread Memory**: `{st.session_state.session_id[:8]}...`")
    
    st.markdown("---")
    if st.button("🗑️ Reset Conversation Memory", use_container_width=True, type="secondary"):
        logfire.warning(f"Memory reset for session: {st.session_state.session_id}")
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
    <div class="nexus-title">NEXUS-RAG</div>
    <div class="nexus-tagline">Agentic Document Intelligence for Reliable Enterprise Search</div>
</div>
""", unsafe_allow_html=True)

# Display history
for message in st.session_state.messages:
    avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Ask about enterprise documentation..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=AI_AVATAR):
        data = {}
        with st.status("⚡ NEXUS-RAG Execution Cycle...", expanded=True) as status_box:
            try:
                with logfire.span("📡 Calling NEXUS-RAG Backend"):
                    url = f"{base_url}/query"
                    payload = {"q": prompt, "thread_id": st.session_state.session_id}
                    response = requests.post(url, json=payload, timeout=90)

                    if response.status_code != 200:
                        st.error(f"Backend Error: {response.status_code} - {response.text}")
                        st.stop()

                    data = response.json()

                steps = data.get("thought_process", [])
                for step in steps:
                    st.write(f"⚙️ {step}")

                status_box.update(label="✅ Response Synthesized", state="complete", expanded=False)

            except Exception as e:
                logfire.error(f"❌ UI-Backend Connection Failed: {e}")
                status_box.update(label="❌ Connection Failed", state="error")
                st.error("Backend Offline.")
                st.stop()

        answer_placeholder = st.empty()
        full_answer = data.get("answer", "No response generated.")

        curr_text = ""
        for char in full_answer:
            curr_text += char
            answer_placeholder.markdown(curr_text + "▌")
            time.sleep(0.003)
        answer_placeholder.markdown(full_answer)

        sources = data.get("sources", [])
        if sources:
            with st.expander(f"📄 Retrieved Context ({len(sources)} chunks)"):
                for i, source in enumerate(sources):
                    st.caption(f"Chunk {i + 1}")
                    st.info(source)
        else:
            st.caption("ℹ️ Response generated from conversational memory or direct synthesis.")

        st.session_state.messages.append({"role": "assistant", "content": full_answer})
        logfire.info("✅ Chat cycle completed successfully.")
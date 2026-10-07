# ==============================================================================
# NEXUS-RAG: Container Image Definition
# ==============================================================================
FROM python:3.11-slim-bookworm

LABEL maintainer="Anuj Kekre"
LABEL description="NEXUS-RAG — Agentic Document Intelligence API"

# Install system dependencies for high-performance extensions
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy production requirements first for efficient layer caching
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements-prod.txt

# Copy application package
COPY app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]


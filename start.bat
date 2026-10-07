@echo off
title NEXUS-RAG - Launching Services
echo ===================================================
echo   NEXUS-RAG: Enterprise Document Intelligence
echo   Architected by Anuj Kekre
echo ===================================================
echo.
cd /d "%~dp0"

echo [1/3] Activating Python virtual environment...
call .\venv\Scripts\activate.bat

echo [2/3] Starting FastAPI Backend on port 8080...
start "NEXUS-RAG Backend (Port 8080)" cmd /k ".\venv\Scripts\uvicorn.exe app.main:app --port 8080 --host 127.0.0.1"

echo Waiting for backend initialization...
timeout /t 4 /nobreak >nul

echo [3/3] Starting Streamlit UI Dashboard on port 8501...
start "NEXUS-RAG Streamlit UI (Port 8501)" cmd /k ".\venv\Scripts\streamlit.exe run ui/app.py --server.port 8501"

echo.
echo ===================================================
echo   NEXUS-RAG is running!
echo   Streamlit UI: http://localhost:8501
echo   API Swagger:  http://127.0.0.1:8080/docs
echo ===================================================
timeout /t 5 >nul

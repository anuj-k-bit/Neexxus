@echo off
title NEXUS-RAG - Evaluation Suite
echo ===================================================
echo   NEXUS-RAG: Evaluation & Benchmarking Portal
echo   Architected by Anuj Kekre
echo ===================================================
echo.
cd /d "%~dp0"

echo Starting Evaluation Dashboard on port 8502...
.\venv\Scripts\streamlit.exe run evals/app.py --server.port 8502

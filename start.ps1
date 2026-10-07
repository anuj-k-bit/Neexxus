# ===================================================
# NEXUS-RAG: 1-Click Launch Script
# Architected by Anuj Kekre
# ===================================================
$ErrorActionPreference = "Continue"
$projectDir = $PSScriptRoot
Set-Location $projectDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  NEXUS-RAG: Enterprise Document Intelligence" -ForegroundColor Cyan
Write-Host "  Architected by Anuj Kekre" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend in background
Write-Host "`n[1/2] Starting FastAPI Backend on port 8080..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/k `".\venv\Scripts\uvicorn.exe app.main:app --port 8080 --host 127.0.0.1`"" -WorkingDirectory $projectDir

Start-Sleep -Seconds 4

# 2. Start Streamlit UI Dashboard
Write-Host "[2/2] Starting Streamlit UI on port 8501..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/k `".\venv\Scripts\streamlit.exe run ui/app.py --server.port 8501`"" -WorkingDirectory $projectDir

Write-Host "`nNEXUS-RAG is running!" -ForegroundColor Cyan
Write-Host "Streamlit UI: http://localhost:8501" -ForegroundColor Yellow
Write-Host "API Swagger:  http://127.0.0.1:8080/docs" -ForegroundColor Yellow

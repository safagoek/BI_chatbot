@echo off
echo Starting DeepBI Agent Development Environment...

:: Start Backend
echo Starting FastAPI Backend...
start cmd /k "cd backend && if exist venv\Scripts\python.exe (venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000) else (python -m uvicorn main:app --reload --port 8000)"

:: Start Frontend
echo Starting Vite Frontend...
start cmd /k "cd frontend && npm run dev"

echo Development environment is starting in separate windows.

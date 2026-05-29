#!/usr/bin/env bash
# run_dev_linux.sh

echo "==================================================="
echo "  Starting DeepBI Agent Development Environment..."
echo "==================================================="
echo

# Function to clean up background processes on exit
cleanup() {
    echo -e "\n[+] Shutting down backend and frontend services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null
    fi
    exit 0
}

# Trap Ctrl+C (SIGINT) and SIGTERM
trap cleanup SIGINT SIGTERM

# Start Backend
echo "[+] Starting FastAPI Backend..."
cd backend
if [ -f "venv/bin/python" ]; then
    venv/bin/python -m uvicorn main:app --reload --port 8000 &
else
    python3 -m uvicorn main:app --reload --port 8000 &
fi
BACKEND_PID=$!
cd ..

# Start Frontend
echo "[+] Starting Vite Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo
echo "[SUCCESS] Services started successfully!"
echo "  - Backend: http://localhost:8000"
echo "  - Frontend: Check Vite's output below"
echo "  - Press Ctrl+C to shut down both services."
echo "==================================================="
echo

# Wait for background processes
wait

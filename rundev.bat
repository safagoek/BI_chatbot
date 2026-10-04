@echo off
setlocal
title DeepBI - Dev Environment

echo.
echo   DeepBI Analytics Studio - Dev Environment
echo   ==========================================
echo.

:: ─── Preflight: venv kontrolu ───
if not exist "backend\venv\Scripts\python.exe" (
    echo [HATA] backend\venv bulunamadi veya bozuk.
    echo         Once rundevsetup.bat calistirin.
    pause
    exit /b 1
)

:: ─── Preflight: node_modules kontrolu ───
if not exist "frontend\node_modules" (
    echo [HATA] frontend\node_modules bulunamadi.
    echo         Once rundevsetup.bat calistirin.
    pause
    exit /b 1
)

:: ─── Preflight: .env kontrolu ───
if not exist "backend\.env" (
    echo [UYARI] backend\.env yok — .env.example'dan kopyalaniyor...
    copy "backend\.env.example" "backend\.env" >nul
)

:: ─── Backend ───
echo [1/2] FastAPI backend baslatiliyor  ^> http://127.0.0.1:8000
start "DeepBI Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: ─── Frontend ───
echo [2/2] Vite frontend baslatiliyor    ^> http://localhost:5173
start "DeepBI Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Iki ayri pencerede baslatildi. Durdurmak icin pencereleri kapatin.
echo Backend health: http://127.0.0.1:8000/api/health
echo.
endlocal

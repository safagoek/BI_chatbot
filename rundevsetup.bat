@echo off
setlocal EnableDelayedExpansion
title DeepBI - Dev Setup
cd /d "%~dp0"

echo.
echo   DeepBI Analytics Studio - Dev Setup
echo   ====================================
echo.

:: ─── 1. Python kontrolu ───
echo [1/5] Python kontrol ediliyor...
where python >nul 2>nul
if !errorlevel! neq 0 (
    echo [HATA] Python bulunamadi. https://www.python.org adresinden kurun ve PATH'e ekleyin.
    goto :fail
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo        %%v

:: ─── 2. Node.js / npm kontrolu ───
echo.
echo [2/5] Node.js / npm kontrol ediliyor...
where npm >nul 2>nul
if !errorlevel! neq 0 (
    echo [HATA] npm bulunamadi. https://nodejs.org adresinden Node.js kurun.
    goto :fail
)
for /f "tokens=*" %%v in ('npm -v') do echo        npm v%%v

:: ─── 3. Backend kurulumu ───
echo.
echo [3/5] Backend kurulumu...
if not exist "backend\venv\Scripts\python.exe" (
    echo        Sanal ortam olusturuluyor: backend\venv
    python -m venv backend\venv
    if !errorlevel! neq 0 (
        echo [HATA] venv olusturulamadi.
        goto :fail
    )
) else (
    echo        venv zaten mevcut, atlandi.
)
echo        Python paketleri yukleniyor (pip install -r requirements.txt)...
backend\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if !errorlevel! neq 0 (
    echo [HATA] pip install basarisiz. Ciktiyi yukaridan kontrol edin.
    goto :fail
)

if not exist "backend\.env" (
    echo        .env olusturuluyor (.env.example kopyalaniyor)...
    copy "backend\.env.example" "backend\.env" >nul
) else (
    echo        .env zaten mevcut, atlandi.
)

:: ─── 4. Frontend kurulumu ───
echo.
echo [4/5] Frontend kurulumu...
echo        npm install calistiriliyor...
pushd frontend
call npm install
if !errorlevel! neq 0 (
    echo [HATA] npm install basarisiz. Ciktiyi yukaridan kontrol edin.
    popd
    goto :fail
)
popd

:: ─── 5. Ozet ───
echo.
echo [5/5] Kurulum tamamlandi!
echo.
echo   Baslatmak icin : rundev.bat
echo   Backend health : http://127.0.0.1:8000/api/health
echo   Frontend       : http://localhost:5173
echo.
choice /c EH /m "Simdi gelistirme ortamini baslat"
if !errorlevel! equ 1 (
    endlocal
    call rundev.bat
    exit /b 0
)
goto :eof

:fail
echo.
echo [FAIL] Kurulum sirasinda hata olustu. Yukaridaki mesajlari kontrol edin.
pause
exit /b 1

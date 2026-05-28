@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   DeepBI Agent Development Environment Setup
echo ===================================================
echo.

:: 1. Check Python
echo [+] Python kontrol ediliyor...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python bulunamadi! Lutfen Python yukleyin ve PATH'e ekleyin.
    goto error
)
python --version

:: 2. Check Node.js / npm
echo.
echo [+] Node.js / npm kontrol ediliyor...
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js veya npm bulunamadi! Lutfen Node.js yukleyin.
    goto error
)
call npm -v

:: 3. Setup Backend
echo.
echo ===================================================
echo   Backend Kurulumu Basliyor...
echo ===================================================
cd backend

:: Create virtual environment if not exists
if not exist venv (
    echo [+] Python Sanal Ortami (venv) olusturuluyor...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Sanal ortam olusturulamadi!
        cd ..
        goto error
    )
) else (
    echo [+] Python Sanal Ortami (venv) zaten mevcut.
)

:: Install requirements
echo [+] Python paketleri (pip) yukleniyor...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Python paketleri yuklenirken hata olustu!
    cd ..
    goto error
)
call deactivate
echo [SUCCESS] Backend bagimliliklari basariyla yuklendi.

:: Copy .env.example if .env does not exist
if not exist .env (
    echo [+] .env dosyasi olusturuluyor (.env.example kopyalaniyor)...
    copy .env.example .env
) else (
    echo [+] .env dosyasi zaten mevcut.
)

cd ..

:: 4. Setup Frontend
echo.
echo ===================================================
echo   Frontend Kurulumu Basliyor...
echo ===================================================
cd frontend

echo [+] Node.js paketleri (npm install) yukleniyor...
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] npm paketleri yuklenirken hata olustu!
    cd ..
    goto error
)
echo [SUCCESS] Frontend bagimliliklari basariyla yuklendi.

cd ..

echo.
echo ===================================================
echo   Kurulum Tamamlandi!
echo ===================================================
echo.
echo Gelistirme ortamini baslatmak icin 'rundev.bat' calistirabilirsiniz.
echo.
set /p choice="Simdi baslatmak ister misiniz? (E/H): "
if /i "%choice%"=="E" (
    echo.
    echo Geliştirme ortami baslatiliyor...
    call rundev.bat
)
goto end

:error
echo.
echo [FAIL] Kurulum sirasinda bir hata olustu. Lutfen yukaridaki hatalari kontrol edin.
pause
exit /b 1

:end
pause

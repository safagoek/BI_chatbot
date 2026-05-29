#!/usr/bin/env bash
# setup_dev_linux.sh
set -e

echo "==================================================="
echo "  DeepBI Agent Development Environment Setup (Linux)"
echo "==================================================="
echo

# 1. Check Python
echo "[+] Checking Python3..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found! Please install python3."
    exit 1
fi
python3 --version

# 2. Check Node.js / npm
echo
echo "[+] Checking Node.js / npm..."
if ! command -v npm &> /dev/null; then
    echo "[ERROR] Node.js or npm could not be found!"
    echo "On CachyOS/Arch Linux, you can install them with: sudo pacman -S nodejs npm"
    echo "Please install them and run this script again."
    exit 1
fi
echo -n "node: " && node -v
echo -n "npm: " && npm -v

# 3. Setup Backend
echo
echo "==================================================="
echo "  Backend Setup Starting..."
echo "==================================================="
cd backend

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "[+] Creating Python Virtual Environment (venv)..."
    python3 -m venv venv
else
    echo "[+] Python Virtual Environment (venv) already exists."
fi

# Install requirements
echo "[+] Installing Python packages (pip)..."
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
deactivate
echo "[SUCCESS] Backend dependencies successfully installed."

# Copy .env.example if .env does not exist
if [ ! -f ".env" ]; then
    echo "[+] Creating .env file (copying .env.example)..."
    cp .env.example .env
else
    echo "[+] .env file already exists."
fi

cd ..

# 4. Setup Frontend
echo
echo "==================================================="
echo "  Frontend Setup Starting..."
echo "==================================================="
cd frontend

echo "[+] Installing Node.js packages (npm install)..."
npm install

echo "[SUCCESS] Frontend dependencies successfully installed."
cd ..

echo
echo "==================================================="
echo "  Setup Complete!"
echo "==================================================="
echo
echo "To activate backend venv in fish shell, run:"
echo "  source backend/venv/bin/activate.fish"
echo
echo "To start the development environment, run './run_dev_linux.sh'"
echo

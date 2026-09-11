@echo off
echo ========================================
echo  DEEP-OS-LOCAL - Iniciando...
echo ========================================
echo.

echo [1/3] Instalando dependencias do backend...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt -q
cd ..

echo [2/3] Instalando dependencias do frontend...
cd frontend
if not exist "node_modules" (
    npm install
)
cd ..

echo [3/3] Iniciando servidores...
echo.
echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5175
echo.

call npm run dev

pause

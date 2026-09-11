@echo off
title Teste Backend

echo.
echo ========================================
echo   Teste de Conexao - Backend
echo ========================================
echo.

cd /d "%~dp0"

echo [1] Verificando se backend esta rodando...
curl -s http://localhost:8001/health 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Backend nao esta respondendo!
    echo.
    echo Inicie o backend primeiro:
    echo   cd backend
    echo   ..\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
    echo.
    pause
    exit /b 1
)

echo.
echo [2] Testando rota de auth...
curl -s http://localhost:8001/auth/me 2>nul
echo.

echo.
echo [3] Testando registro...
curl -s -X POST http://localhost:8001/auth/register -H "Content-Type: application/json" -d "{\"name\":\"teste\",\"email\":\"teste@teste.com\",\"password\":\"123456\"}" 2>nul
echo.

echo.
echo ========================================
echo   Backend funcionando!
echo ========================================
echo.
pause

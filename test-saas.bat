@echo off
title DEEP-OS SaaS Test

echo.
echo ========================================
echo   DEEP-OS SaaS - Teste Rapido
echo ========================================
echo.

cd /d "%~dp0"

set PYTHON=venv\Scripts\python.exe

echo [1] Testando banco de dados...
if exist "data\admin.db" (
    echo     OK - admin.db existe
) else (
    echo     Criando admin.db...
    "%PYTHON%" backend\init_admin_db.py
)

echo.
echo [2] Testando importacao do backend...
cd backend
"%PYTHON%" -c "from core.auth import AuthManager; print('     OK - Auth carregado')"
"%PYTHON%" -c "from models.tenant import Tenant; print('     OK - Tenant carregado')"
"%PYTHON%" -c "from models.plan import Plan; print('     OK - Plan carregado')"
"%PYTHON%" -c "from middleware.tenant import TenantMiddleware; print('     OK - Middleware carregado')"
cd ..

echo.
echo [3] Verificando porta 8001...
netstat -an | findstr ":8001" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo     OK - Backend ja esta rodando
) else (
    echo     Backend nao está rodando
)

echo.
echo [4] Verificando porta 5176...
netstat -an | findstr ":5176" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo     OK - Frontend SaaS ja esta rodando
) else (
    echo     Frontend SaaS nao esta rodando
)

echo.
echo ========================================
echo   Para iniciar: start-saas.bat
echo   Acesse: http://localhost:5176
echo ========================================
echo.
pause

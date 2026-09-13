@echo off
chcp 65001 >nul 2>&1
title DEEP-OS-LOCAL SaaS
color 0A

cd /d "%~dp0"

echo ============================================
echo   DEEP-OS-LOCAL SaaS
echo ============================================
echo.

:: Matar processos antigos
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: ===========================================================================
::  [1/4] llama-server (modelos GGUF locais, porta 8080)
::
::  ESTE PASSO NAO EXISTIA AQUI — mesma correcao feita no DEEP-OS.
::
::  Sem ele o sistema abria sem NENHUM modelo GGUF: a lista aparecia na tela e
::  nada respondia, porque nao havia servidor na porta 8080. (O backend sabe
::  subir o llama-server sozinho, mas so quando o usuario escolhe um modelo na
::  interface.)
::
::  O modelo e escolhido pelo escolher-modelo.bat (ordem de preferencia, ou o
::  que estiver em models\preferido.txt).
:: ===========================================================================
echo [1/4] Iniciando llama-server GGUF (porta 8080)...
set "MODEL_GGUF="
for /f "usebackq delims=" %%f in (`call "%~dp0escolher-modelo.bat" 2^>nul`) do (
    if not defined MODEL_GGUF set "MODEL_GGUF=%%f"
)

if defined MODEL_GGUF (
    if not exist "bin\vulkan\llama-server.exe" (
        echo  [AVISO] bin\vulkan\llama-server.exe nao encontrado — pulando o GGUF.
    ) else (
        REM -1 = AUTO: o llama.cpp decide quantas camadas cabem na placa.
        REM Nao fixe um numero: o usuario troca de placa de video e o numero
        REM teria de mudar junto. Com -1 o mesmo comando serve para 8, 12 ou 24 GB.
        set "GPU_FLAG=--n-gpu-layers -1"
        findstr /i "gpu_enabled: false" backend\config.yaml >nul 2>&1
        if %errorlevel% equ 0 set "GPU_FLAG="
        echo  Modelo: %MODEL_GGUF%
        start "LLamaCPP :8080" cmd /c "bin\vulkan\llama-server.exe" --model "%MODEL_GGUF%" --port 8080 --ctx-size 8192 --host 0.0.0.0 %GPU_FLAG%
        timeout /t 6 /nobreak >nul
        echo  OK
    )
) else (
    echo  [AVISO] Nenhum modelo .gguf encontrado. Coloque um em models\gguf\
    echo          O resto do sistema funciona; os modelos GGUF nao.
)

:: Backend
echo [2/4] Iniciando Backend (porta 8001)...
start "Backend" cmd /k "cd /d C:\DEEP-OS-LOCAL\backend && call venv\Scripts\activate && uvicorn main:app --host 127.0.0.1 --port 8001 --reload --reload-dir routes"
timeout /t 5 /nobreak >nul

:: Chatbot
echo [3/4] Iniciando Chatbot Gateway (porta 8010)...
start "Chatbot" cmd /k "cd /d C:\DEEP-OS-LOCAL\chatbot-server && node server.js"
timeout /t 3 /nobreak >nul

:: Frontend SaaS
echo [4/4] Iniciando Frontend SaaS (porta 5176)...
start "Frontend" cmd /k "cd /d C:\DEEP-OS-LOCAL\frontend && npx vite --mode saas --port 5176"
timeout /t 5 /nobreak >nul

:: Abrir navegador
start http://localhost:5176

echo.
echo ============================================
echo   Backend:  http://localhost:8001
echo   Chatbot:  http://localhost:8010
echo   Frontend: http://localhost:5176
if defined MODEL_GGUF echo   LLamaCPP: http://localhost:8080/v1
if defined MODEL_GGUF echo   Modelo:   %MODEL_GGUF%
echo ============================================
echo.
echo  Para fechar: STOP-TOTAL.bat
echo.
pause

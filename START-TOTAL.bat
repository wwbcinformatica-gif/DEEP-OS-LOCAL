@echo off
title DEEP-OS - Inicializacao Unificada
cd /d "%~dp0"

echo ============================================
echo     DEEP-OS - Inicializacao Unificada
echo ============================================
echo.

REM 1. Mata processos antigos do DEEP-OS
echo [1/6] Limpando processos antigos...
taskkill /FI "WINDOWTITLE eq WBC Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq WBC Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq LLamaCPP*" /F >nul 2>&1
timeout /t 2 /nobreak >nul
echo  OK

REM 2. Verifica dependencias
echo [2/6] Verificando dependencias...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] npm nao encontrado. Instale Node.js.
    pause
    exit /b 1
)
if not exist "venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado. Execute Instalar_Dependencias.bat
    pause
    exit /b 1
)
echo  OK

REM 3. Inicia llama-server com GGUF (porta 8080)
echo [3/6] Iniciando llama-server GGUF (porta 8080)...
set "MODEL_GGUF="
:: Busca qualquer .gguf na pasta models/gguf
for %%f in (models\gguf\*.gguf) do (
    if not "%%~nxf"=="%%f" (
        set "MODEL_GGUF=%%~ff"
    )
)
:: Se nao encontrou na subpasta, busca na raiz models/
if not defined MODEL_GGUF (
    for %%f in (models\*.gguf) do (
        set "MODEL_GGUF=%%~ff"
    )
)

if defined MODEL_GGUF (
    set "GPU_FLAG="
    :: Verifica se GPU esta habilitada no config
    findstr /i "gpu_enabled: true" config.yaml >nul 2>&1
    if %errorlevel% equ 0 (
        set "GPU_FLAG=--n-gpu-layers 999"
    )
    start "LLamaCPP :8080" cmd /c "bin\vulkan\llama-server.exe" --model "%MODEL_GGUF%" --port 8080 --ctx-size 8192 --host 0.0.0.0 %GPU_FLAG%
    timeout /t 5 /nobreak >nul
    echo  OK - Modelo: %MODEL_GGUF%
) else (
    echo  AVISO: Nenhum modelo .gguf encontrado em models\
)

REM 4. Inicia Backend (porta 8001)
echo [4/6] Iniciando Backend (FastAPI + WebSocket)...
set "BACKEND_DIR=%~dp0backend"
set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
cd /d "%BACKEND_DIR%"
start "WBC Backend :8001" cmd /c "%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level warning
timeout /t 4 /nobreak >nul
echo  OK

REM 5. Inicia Frontend (porta 5175)
echo [5/6] Iniciando Frontend (Vite + React)...
set "FRONTEND_DIR=%~dp0frontend"
cd /d "%FRONTEND_DIR%"
start "WBC Frontend :5175" cmd /c npm run dev
timeout /t 3 /nobreak >nul
echo  OK

REM 6. Abre navegador
echo [6/6] Abrindo navegador...
cd /d "%~dp0"
start "" "http://localhost:5175"

echo.
echo ============================================
echo  Tudo pronto!
echo  Backend:    http://localhost:8001
echo  Frontend:   http://localhost:5175
echo  LLamaCPP:   http://localhost:8080/v1
if defined MODEL_GGUF echo  Modelo:     %MODEL_GGUF%
echo  Terminal Web integrado em /ws/terminal
echo ============================================
echo.
echo  Para encerrar tudo, execute STOP-TOTAL.bat
echo.
echo  Pressione qualquer tecla para ocultar esta janela...
pause >nul
exit

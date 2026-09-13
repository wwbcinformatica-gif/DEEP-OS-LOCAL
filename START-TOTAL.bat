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
taskkill /f /im llama-server.exe >nul 2>&1
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
REM Quem escolhe o modelo e o escolher-modelo.bat.
REM
REM ANTES este trecho fazia o laco abaixo, que estava ERRADO:
REM     for %%f in (models\gguf\*.gguf) do (
REM         if not "%%~nxf"=="%%f" ( set "MODEL_GGUF=%%~ff" )
REM     )
REM `%%~nxf` e so o NOME e `%%f` e o caminho COMPLETO: a comparacao nunca era
REM igual, o `if` era sempre verdadeiro e o laco ficava com o ULTIMO arquivo.
REM Ou seja: o modelo carregado era loteria. Agora a ordem de preferencia e
REM explicita e da para fixar um modelo em models\preferido.txt.
set "MODEL_GGUF="
for /f "usebackq delims=" %%f in (`call "%~dp0escolher-modelo.bat" 2^>nul`) do (
    if not defined MODEL_GGUF set "MODEL_GGUF=%%f"
)

if defined MODEL_GGUF (
    call :gpu_flag
    start "LLamaCPP :8080" cmd /c "bin\vulkan\llama-server.exe" --model "%MODEL_GGUF%" --port 8080 --ctx-size 8192 --host 0.0.0.0 %GPU_FLAG%
    timeout /t 5 /nobreak >nul
    echo  OK - Modelo: %MODEL_GGUF%
) else (
    echo  AVISO: Nenhum modelo .gguf encontrado em models\
)
goto :depois_llama

:gpu_flag
REM -1 = AUTO: o llama.cpp decide quantas camadas cabem na placa.
REM
REM ANTES era "--n-gpu-layers 999" (todas as camadas na GPU). Numa RTX 3060 de
REM 12 GB isso derrubava o carregamento de modelos grandes:
REM     ggml_vulkan: vk::Device::allocateMemory: ErrorOutOfDeviceMemory
REM Com -1 o modelo de 27B (13 GB) carrega, jogando na CPU o que nao couber.
REM
REM NAO fixe um numero aqui: o usuario troca de placa e o numero teria de mudar
REM junto. Com -1 o mesmo comando serve para 8, 12 ou 24 GB.
set "GPU_FLAG=--n-gpu-layers -1"
REM O CAMINHO e backend\config.yaml, NAO o config.yaml da raiz.
REM ANTES apontava para "config.yaml" (raiz), que nao tem a chave gpu_enabled —
REM entao o findstr NUNCA casava e a deteccao nao funcionava em projeto nenhum.
REM Quem le esse arquivo em runtime e backend/routes/llamacpp_route.py.
findstr /i "gpu_enabled: false" "%~dp0backend\config.yaml" >nul 2>&1
if %errorlevel% equ 0 set "GPU_FLAG="
exit /b

:depois_llama

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

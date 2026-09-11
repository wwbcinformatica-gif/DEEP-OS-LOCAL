@echo off
chcp 65001 >nul 2>&1
title Instalar Dependencias - DEEP-OS
color 0A

echo ============================================
echo   INSTALAR DEPENDENCIAS - DEEP-OS
echo ============================================
echo.

:: Detecta pasta do projeto
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: Verifica Python
echo [1/5] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       [ERRO] Python nao encontrado!
    echo       Instale Python 3.11+ de: https://www.python.org/downloads/
    echo       IMPORTANTE: Marque "Add Python to PATH" na instalacao!
    echo.
    pause
    exit /b 1
)

:: Verifica se Python e 64-bit (recomendado para GPU)
for /f "tokens=*" %%i in ('python -c "import sys; print(1 if sys.maxsize > 2**32 else 0)"') do set IS_64BIT=%%i

if "%IS_64BIT%"=="0" (
    echo       [AVISO] Python 32-bit detectado. GPU pode nao funcionar.
    echo       Recomendado: Python 3.11 64-bit
    echo.
)

python --version
echo.

:: Verifica se ja existe venv
echo [2/5] Verificando ambiente virtual...
if exist "%PROJECT_DIR%venv\Scripts\python.exe" (
    echo       venv ja existe. Recriando...
    rmdir /s /q "%PROJECT_DIR%venv" 2>nul
)

:: Cria venv
echo [3/5] Criando ambiente virtual...
python -m venv "%PROJECT_DIR%venv"
if %errorlevel% neq 0 (
    echo       [ERRO] Falha ao criar venv!
    pause
    exit /b 1
)
echo       venv criado com sucesso!
echo.

:: Atualiza pip
echo [4/5] Atualizando pip...
"%PROJECT_DIR%venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
echo       pip atualizado!
echo.

:: Instala dependencias
echo [5/5] Instalando dependencias...
echo       Isso pode demorar alguns minutos...
echo.
if exist "%PROJECT_DIR%backend\requirements.txt" (
    "%PROJECT_DIR%venv\Scripts\pip.exe" install -r "%PROJECT_DIR%backend\requirements.txt"
    if %errorlevel% neq 0 (
        echo.
        echo       [AVISO] Algumas dependencias podem ter falhado.
        echo       O sistema pode funcionar parcialmente.
    )
) else (
    echo       [AVISO] requirements.txt nao encontrado em backend\
    echo       Instalando pacotes essenciais manualmente...
    "%PROJECT_DIR%venv\Scripts\pip.exe" install fastapi uvicorn pydantic google-genai python-multipart websockets aiohttp pyyaml
)

:: Verifica instalacao
echo.
echo ============================================
echo   Verificando instalacao...
echo ============================================
echo.

"%PROJECT_DIR%venv\Scripts\python.exe" -c "import sys; print(f'Python: {sys.version}'); print(f'Bits: {chr(34)}64-bit{chr(34) if sys.maxsize > 2**32 else chr(34)}32-bit{chr(34)}')"

echo.
echo Verificando pacotes principais...
"%PROJECT_DIR%venv\Scripts\python.exe" -c "import fastapi; print(f'  fastapi: {fastapi.__version__}')"
"%PROJECT_DIR%venv\Scripts\python.exe" -c "import uvicorn; print(f'  uvicorn: {uvicorn.__version__}')"
"%PROJECT_DIR%venv\Scripts\python.exe" -c "import pydantic; print(f'  pydantic: {pydantic.__version__}')"
"%PROJECT_DIR%venv\Scripts\python.exe" -c "import google.genai; print('  google-genai: OK')"

echo.
echo Verificando GPU (nvidia-smi)...
:: Busca nvidia-smi em varios locais possiveis
set "NVIDIA_SMI="
where nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    set "NVIDIA_SMI=nvidia-smi"
) else (
    if exist "C:\Windows\System32\nvidia-smi.exe" (
        set "NVIDIA_SMI=C:\Windows\System32\nvidia-smi.exe"
    ) else (
        if exist "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe" (
            set "NVIDIA_SMI=C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        )
    )
)

if defined NVIDIA_SMI (
    "%NVIDIA_SMI%" --query-gpu=name,memory.total --format=csv,nounits,noheader
) else (
    echo   GPU: nvidia-smi nao encontrado (normal se nao tiver GPU NVIDIA)
)

echo.
echo ============================================
echo   Instalacao concluida!
echo ============================================
echo.
echo Para iniciar o DEEP-OS:
echo   C:\DEEP-OS\START-TOTAL.bat
echo.
echo Para iniciar apenas o backend:
echo   cd backend
echo   ..\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001
echo.
pause

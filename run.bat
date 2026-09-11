@echo off
REM â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
REM  DEEP-OS â€” Quick Start Script
REM  Comandos: run-tests, run-agent, run-server, clear-memory, help
REM â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

setlocal enabledelayedexpansion

set "BACKEND=%~dp0backend"
set "PYTHON=python"

if "%1"=="" goto :help
if "%1"=="help" goto :help
if "%1"=="--help" goto :help
if "%1"=="-h" goto :help
if "%1"=="run-tests" goto :run_tests
if "%1"=="test" goto :run_tests
if "%1"=="run-agent" goto :run_agent
if "%1"=="agent" goto :run_agent
if "%1"=="run-server" goto :run_server
if "%1"=="server" goto :run_server
if "%1"=="start" goto :run_server
if "%1"=="clear-memory" goto :clear_memory
if "%1"=="clear" goto :clear_memory
if "%1"=="stats" goto :show_stats
if "%1"=="diagnostics" goto :show_diagnostics

echo [ERRO] Comando desconhecido: %1
echo.
goto :help

REM â”€â”€â”€ run-tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:run_tests
echo.
echo ========================================
echo  DEEP-OS â€” Executando Testes
echo ========================================
echo.
%PYTHON% "%BACKEND%\tests\test_resilience.py"
echo.
if %ERRORLEVEL% EQU 0 (
    echo [OK] Todos os testes passaram.
) else (
    echo [FALHA] Alguns testes falharam.
)
goto :eof

REM â”€â”€â”€ run-agent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:run_agent
echo.
echo ========================================
echo  DEEP-OS â€” CLI Monitor Interativo
echo ========================================
echo.
if "%2"=="" (
    set /p "TASK=Digite a tarefa: "
) else (
    set "TASK=%~2"
)
%PYTHON% -m cli.monitor "!TASK!" --provider groq --model llama-3.1-70b-versatile
goto :eof

REM â”€â”€â”€ run-server â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:run_server
echo.
echo ========================================
echo  DEEP-OS â€” Iniciando Servidor
echo ========================================
echo.
%PYTHON% "%BACKEND%\main.py"
goto :eof

REM â”€â”€â”€ clear-memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:clear_memory
echo.
echo ========================================
echo  DEEP-OS â€” Limpando Memoria
echo ========================================
echo.
%PYTHON% -c "import asyncio, sys; sys.path.insert(0, '%BACKEND%'); from memory.elastic_memory import clear_long_term_memory; asyncio.run(clear_long_term_memory()); print('Memoria de longo prazo limpa.')"
goto :eof

REM â”€â”€â”€ stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:show_stats
echo.
echo ========================================
echo  DEEP-OS â€” Estatisticas
echo ========================================
echo.
%PYTHON% -c "import asyncio, sys; sys.path.insert(0, '%BACKEND%'); from memory.elastic_memory import get_memory_stats; import json; print(json.dumps(asyncio.run(get_memory_stats()), indent=2))"
goto :eof

REM â”€â”€â”€ diagnostics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:show_diagnostics
echo.
echo ========================================
echo  DEEP-OS â€” Diagnostics
echo ========================================
echo.
echo Buscando anti-padroes no index.json...
%PYTHON% -c "import json, sys; sys.path.insert(0, '%BACKEND%'); from core.config import MEMORY_DIR; f=MEMORY_DIR/\"long_term\"/\"index.json\"; data=json.load(open(f,encoding=\"utf-8\")) if f.exists() else []; failures=[e for e in data if e.get(\"is_failure\")]; print(f'Total: {len(data)} entradas'); print(f'Falhas: {len(failures)}'); [print(f'  - {e[\"task\"][:60]} ({e.get(\"timestamp\",\"?\")[:10]})') for e in failures[-5:]]"
goto :eof

REM â”€â”€â”€ help â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:help
echo.
echo  DEEP-OS â€” Quick Start
echo  ============================
echo.
echo  Comandos:
echo    run-tests        Executa os 86 testes de resilencia
echo    run-agent [tarea] Inicia o CLI monitor interativo
echo    run-server       Inicia o servidor FastAPI
echo    clear-memory     Limpa o index.json de memorias
echo    stats            Mostra estatisticas da memoria
echo    diagnostics      Mostra anti-padroes registrados
echo    help             Exibe esta ajuda
echo.
echo  Exemplos:
echo    run.bat run-tests
echo    run.bat run-agent "criar endpoint FastAPI"
echo    run.bat run-server
echo    run.bat clear-memory
echo.
goto :eof

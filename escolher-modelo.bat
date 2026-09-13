@echo off
REM ============================================================================
REM  Escolhe qual modelo GGUF o llama-server vai carregar.
REM
REM  POR QUE ESTE ARQUIVO EXISTE
REM  O START-TOTAL.bat escolhia o modelo assim:
REM
REM      for %%f in (models\gguf\*.gguf) do (
REM          if not "%%~nxf"=="%%f" (
REM              set "MODEL_GGUF=%%~ff"
REM          )
REM      )
REM
REM  `%%~nxf` e so o NOME do arquivo e `%%f` e o caminho COMPLETO, entao a
REM  comparacao NUNCA e igual -> o `if` e sempre verdadeiro -> o laco sobrescreve
REM  a variavel a cada arquivo e o ULTIMO (ordem alfabetica) sempre vence.
REM  Resultado: o modelo carregado era uma loteria, e nao o que o usuario queria.
REM
REM  Uso:  escolher-modelo.bat
REM  Saida: o caminho completo do .gguf escolhido (ou nada, se nao houver nenhum)
REM
REM  COMO TROCAR DE MODELO SEM EDITAR ESTE ARQUIVO
REM  Crie o arquivo models\preferido.txt com o nome do arquivo que voce quer,
REM  por exemplo:   Qwen3.8-27B-UD-IQ4_XS.gguf
REM ============================================================================

setlocal enabledelayedexpansion

REM %~dp0 termina com "\", entao a pasta models fica assim:
set "PASTA=%~dp0models"

if not exist "%PASTA%\gguf" goto :fim

REM ── 1. Preferencia explicita do usuario (models\preferido.txt) ──────────────
if exist "%PASTA%\preferido.txt" (
    set /p QUERIDO=<"%PASTA%\preferido.txt"
    if defined QUERIDO (
        REM Nao usamos "dir /s": a pasta models e um ATALHO (junction) para outra
        REM unidade, e varrer recursivamente por dentro do atalho e lento e
        REM desnecessario — os modelos ficam em models\gguf, um nivel so.
        for %%f in ("%PASTA%\gguf\!QUERIDO!") do (
            if exist "%%~ff" (
                echo %%~ff
                goto :fim
            )
        )
        echo AVISO: models\preferido.txt pede "!QUERIDO!" mas nao achei o arquivo. 1>&2
    )
)

REM ── 2. Ordem de preferencia (do melhor para o mais simples) ────────────────
REM  O primeiro que existir vence. Os arquivos podem estar em models\gguf ou
REM  numa subpasta dela (ex.: gguf\27B), entao tentamos os dois niveis.
REM  ESTA ORDEM FOI TESTADA NESTA MAQUINA (RTX 3060 12 GB, 12 GB de RAM):
REM    Llama-3.2-3B (1,88 GB) .......... CARREGOU em 12s
REM    Qwen2.5-7B   (4,36 GB) .......... CARREGOU em 18s
REM    NemoMix-12B  (6,96 GB) .......... CARREGOU em 42s
REM    Qwen3.8-27B-IQ3_S (11,21 GB) .... FALHOU (ErrorOutOfDeviceMemory)
REM    Qwen3.8-27B-IQ4_XS (13,27 GB) ... FALHOU (maior que a VRAM da placa)
REM
REM  Os 27B NAO entram: com 11 a 13 GB de pesos sobram ~1 GB na placa, e o
REM  llama.cpp precisa de mais que isso para o cache de contexto. Colocar um
REM  deles aqui so faria o llama-server morrer no start.
REM  (Para usa-los: reduzir --n-gpu-layers e rodar parte na CPU, ou usar uma
REM   quantizacao menor.)
for %%n in (
    "NemoMix-Unleashed-12B-Q4_K_M.gguf"
    "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    "Llama-3.2-3B-Instruct-Q4_K_M.gguf"
    "bonsai.gguf"
) do (
    call :procurar "%%~n"
    if defined ACHOU goto :achou
)

REM ── 3. Ultimo recurso: qualquer .gguf na raiz de models\gguf ───────────────
REM  Aqui pegamos o PRIMEIRO (nao o ultimo) — era exatamente esse o defeito do
REM  script antigo, que ficava com o ultimo arquivo do laco.
for %%f in ("%PASTA%\gguf\*.gguf") do (
    if not defined ACHOU set "ACHOU=%%~ff"
)
if defined ACHOU goto :achou

goto :fim

:procurar
set "ACHOU="
if exist "%PASTA%\gguf\%~1" set "ACHOU=%PASTA%\gguf\%~1"
if not defined ACHOU (
    for /d %%d in ("%PASTA%\gguf\*") do (
        if not defined ACHOU if exist "%%~fd\%~1" set "ACHOU=%%~fd\%~1"
    )
)
exit /b

:achou
echo %ACHOU%

:fim
endlocal

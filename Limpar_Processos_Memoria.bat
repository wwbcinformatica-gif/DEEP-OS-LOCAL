@echo off
chcp 65001 >nul 2>&1
title Limpar Memoria - DEEP-OS
color 0A

echo ========================================
echo   LIMPAR MEMORIA - DEEP-OS
echo ========================================
echo.

:: Mostra uso de memoria antes
echo [ANTES] Top 5 processos por memoria:
powershell -NoProfile -Command "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize"
echo.

:: Para o llama-server (maior consumidor)
echo [1/4] Parando llama-server...
taskkill /f /im llama-server.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo       llama-server encerrado
) else (
    echo       llama-server nao estava rodando
)

:: Para processos Node.js do DEEP-OS (usa titulos das janelas)
echo [2/4] Parando processos Node.js do DEEP-OS...
taskkill /FI "WINDOWTITLE eq WBC Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq WBC Backend*" /F >nul 2>&1
echo       processos Node encerrados

:: Limpa cache do Windows
echo [3/4] Limpando cache do Windows...
del /q /s "%TEMP%\*.tmp" >nul 2>&1
del /q /s "%TEMP%\*.log" >nul 2>&1
del /q /s "%TEMP%\*.cache" >nul 2>&1
echo       temporarios limpos

:: Forca liberar memoria de processos grandes do DEEP-OS
echo [4/4] Liberando memoria de processos DEEP-OS...
powershell -NoProfile -Command "
    Get-Process | Where-Object {
        $_.Name -match 'python|node|llama' -and
        $_.WorkingSet64 -gt 50MB
    } | ForEach-Object {
        try {
            [System.GC]::Collect()
            [System.GC]::WaitForPendingFinalizers()
        } catch {}
    }
"
echo       cache liberado

echo.
echo ========================================
echo [DEPOIS] Top 5 processos por memoria:
echo ========================================
powershell -NoProfile -Command "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize"

echo.
echo ========================================
echo   Limpeza concluida!
echo ========================================
echo.
echo Pressione qualquer tecla para fechar...
pause >nul

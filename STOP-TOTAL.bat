@echo off
echo Parando DEEP-OS-LOCAL...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
echo Pronto!
pause

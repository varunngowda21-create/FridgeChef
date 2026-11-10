@echo off
title FridgeChef AI - Backend API (Port 8000)
echo =====================================================================
echo  Starting FridgeChef AI Backend API Server
echo  URL: http://127.0.0.1:8000
echo  Docs: http://127.0.0.1:8000/docs
echo =====================================================================
echo.

cd /d "%~dp0api"

:: First try WSL (most reliable across Windows DLL configurations)
where wsl >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Launching via WSL environment bridge...
    wsl -d Ubuntu -e bash -c "cd '/mnt/c/Users/chara/Desktop/Fridge project/api' && ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    if %ERRORLEVEL% EQU 0 goto :done
)

:: Fallback to native Windows virtualenv
echo Launching via native Windows virtualenv...
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload

:done
pause


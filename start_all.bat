@echo off
title FridgeChef AI Launcher
echo =====================================================================
echo  FRIDGECHEF AI — LOCAL DEMONSTRATION LAUNCHER
echo =====================================================================
echo.
echo Starting Backend API and Frontend UI in separate windows...
echo.

:: Launch Backend
start "FridgeChef Backend" cmd /k "%~dp0start_backend.bat"

:: Brief pause to let backend initialize database connection
echo Waiting for backend API to initialize...
timeout /t 4 /nobreak >nul

:: Launch Frontend
start "FridgeChef Frontend" cmd /k "%~dp0start_frontend.bat"

:: Brief pause then launch default browser
timeout /t 3 /nobreak >nul
echo Opening FridgeChef in browser...
start http://localhost:5173

echo.
echo =====================================================================
echo  FridgeChef is now running!
echo  - Web Application: http://localhost:5173
echo  - Swagger API Docs: http://127.0.0.1:8000/docs
echo =====================================================================
echo.
pause


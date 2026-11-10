@echo off
title FridgeChef AI - Frontend UI (Port 5173)
echo =====================================================================
echo  Starting FridgeChef AI Web Interface
echo  URL: http://localhost:5173
echo =====================================================================
echo.

cd /d "%~dp0web"
npm run dev

pause


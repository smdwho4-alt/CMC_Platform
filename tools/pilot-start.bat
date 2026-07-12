@echo off
title CSHSP Pilot Start

echo ======================================
echo    CSHSP Pilot Start
echo ======================================
echo.

echo [1/4] Starting API Server...
start "CSHSP API" powershell -NoExit -Command "cd ..; python -m uvicorn src.api.api_server:app --host 127.0.0.1 --port 8600"

timeout /t 3 >nul

echo [2/4] Starting Frontend...
start "CSHSP Frontend" powershell -NoExit -Command "cd ..; python -m http.server 4000"

timeout /t 2 >nul

echo [3/4] Opening Dashboard...
start http://127.0.0.1:4000/app/pages/admin_dashboard_new.html

echo [4/4] Opening Reservation...
start http://127.0.0.1:4000/app/pages/reservation_new.html

echo.
echo ======================================
echo Pilot Start Complete
echo ======================================
pause

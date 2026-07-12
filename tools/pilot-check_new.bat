@echo off
rem ============================================================
rem  CSHSP Operation Toolkit v1.0.2 - pilot-check_new.bat
rem  Double-click to run the CSHSP Pilot health check.
rem  All logic lives in pilot-check_new.ps1 / settings_new.ps1
rem
rem  Do NOT use "chcp 65001" here. This bat prints no Korean
rem  text, and the PowerShell scripts print Hangul via the
rem  Unicode console API. Switching the codepage to 65001 breaks
rem  Hangul rendering on Korean Windows (PS5.1 + conhost font bug).
rem ============================================================
title CSHSP Pilot Check
setlocal
set "PSFILE=%~dp0pilot-check_new.ps1"

where pwsh >nul 2>&1
if %errorlevel%==0 (
    pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PSFILE%"
) else (
    powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PSFILE%"
)

echo.
pause
endlocal

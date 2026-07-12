@echo off
rem ============================================================
rem  CSHSP Operation Toolkit v1.0 - pilot-start_new.bat
rem  Double-click to start the CSHSP Pilot (API + Frontend).
rem  All logic lives in pilot-start_new.ps1 / settings_new.ps1
rem
rem  [v1.0.1] Do NOT use "chcp 65001" here. This bat prints no
rem  Korean text, and the PowerShell scripts print Hangul via the
rem  Unicode console API. Switching the codepage to 65001 breaks
rem  Hangul rendering on Korean Windows (PS5.1 + conhost font bug).
rem ============================================================
title CSHSP Pilot Start
setlocal
set "PSFILE=%~dp0pilot-start_new.ps1"

where pwsh >nul 2>&1
if %errorlevel%==0 (
    pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PSFILE%"
) else (
    powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PSFILE%"
)

echo.
pause
endlocal

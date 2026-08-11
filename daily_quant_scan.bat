@echo off
TITLE Daily Quant Scan - Strategic Briefing
SETLOCAL EnableDelayedExpansion
chcp 65001 >nul

:: ============================================================================
:: Daily quant scan -> Strategic_Briefing_Automated.pdf
::
:: FIXED 11-Aug-2026. This file had been dead for a long time and failed
:: silently, because `cd /d` to a missing path does not stop a batch — it just
:: leaves you in the wrong directory and every following line runs there:
::   - cd /d "e:\Gemini\VS Code"   <- that drive/folder no longer exists
::   - python quant_analyst.py     <- bare `python` = global 3.14, NOT the venv
:: So it ran the wrong interpreter, in the wrong folder, against a different
:: pandas than the app uses, and reported "Done!" regardless.
::
:: Three changes: the real project path, the TradingData venv, and each step
:: is CHECKED so a failure stops the run instead of producing a stale PDF.
:: ============================================================================

SET "PROJECT_DIR=C:\Users\jayra\Documents\GeminiVSCode"
SET "PYTHON_EXE=C:\Users\jayra\TradingData\venv\Scripts\python.exe"

IF NOT EXIST "%PROJECT_DIR%" (
    echo [ERROR] Project folder not found: %PROJECT_DIR%
    pause & exit /b 1
)
IF NOT EXIST "%PYTHON_EXE%" (
    echo [ERROR] Python not found: %PYTHON_EXE%
    echo         The venv lives in TradingData, NOT in the project folder.
    pause & exit /b 1
)

:: Both scripts read and write by RELATIVE path (Strategic_Briefing_AI.md,
:: Strategic_Briefing_Automated.pdf), so the working directory decides where
:: the output lands. This is the line that was wrong.
cd /d "%PROJECT_DIR%"

SET "PYTHONIOENCODING=utf-8"
SET "PYTHONUTF8=1"

echo.
echo   DAILY QUANT SCAN
echo   project : %PROJECT_DIR%
echo   python  : %PYTHON_EXE%
echo.

:: Pre-flight: undefined names on the live path (see preflight.py). Unattended
:: mode never blocks and always exits 0 — findings go to logs\preflight.log
:: and Telegram.
"%PYTHON_EXE%" preflight.py --unattended

echo   [1/2] Hybrid Analyst Engine...
"%PYTHON_EXE%" quant_analyst.py
IF ERRORLEVEL 1 (
    echo.
    echo   [ERROR] quant_analyst.py failed - STOPPING.
    echo   Generating the PDF now would just re-publish yesterday's briefing
    echo   under today's date, which is worse than no briefing.
    pause & exit /b 1
)

echo   [2/2] Strategic Briefing PDF...
"%PYTHON_EXE%" generate_report_pdf.py
IF ERRORLEVEL 1 (
    echo.
    echo   [ERROR] generate_report_pdf.py failed - see the trace above.
    pause & exit /b 1
)

echo.
echo   Done - Strategic_Briefing_Automated.pdf
echo   %PROJECT_DIR%\Strategic_Briefing_Automated.pdf
echo.
timeout /t 5

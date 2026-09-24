@echo off
REM ===========================================================================
REM  Daily docs truth check  (Task Scheduler: Docs_Truth_Check, 17:15 Mon-Fri)
REM
REM  Headless twin of DOCS_TRUTH_CHECK.bat (that one ends in `pause`, which
REM  would hang a scheduled run). Diffs 49 code facts against the accepted
REM  baseline and names the Library pages that cite anything that moved.
REM  Never edits. Exit 1 = a fact moved: read logs\docs_truth.log, fix the
REM  pages, then DOCS_TRUTH_CHECK.bat --accept. Scheduled 24-Sep-2026
REM  (audit AUD-OPS-03: Doc 26 listed it as a daily job it never was).
REM ===========================================================================
setlocal
set "PROJ=C:\Users\jayra\Documents\GeminiVSCode"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
cd /d "%PROJ%" || exit /b 2
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
echo ==== %date% %time% ==== >> logs\docs_truth.log
"%PY%" docs_audit\truth_watch.py >> logs\docs_truth.log 2>&1
exit /b %errorlevel%

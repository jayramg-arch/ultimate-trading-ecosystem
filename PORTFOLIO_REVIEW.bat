@echo off
REM ===========================================================================
REM  PORTFOLIO REVIEW - every holding read by the AI Reviewer with the same depth
REM  as a new trade, on the DAILY chart (31-Oct-2026)
REM
REM  Per holding: the full S4 + S5 read, the SL Dashboard's own numbers (stops,
REM  thesis, Chandelier, R, drawdown, worst gap, earnings, ladder), and a ruling
REM  HOLD / ADD / TRIM / REDUCE / EXIT with the new INVALIDATION, STOP, DRAWDOWN
REM  and OPPORTUNITY. Proposals only - nothing is placed or written to the journal.
REM
REM    PORTFOLIO_REVIEW.bat                     every holding
REM    PORTFOLIO_REVIEW.bat --symbols A,B       only these
REM    PORTFOLIO_REVIEW.bat --telegram          + the summary on Telegram
REM
REM  With the S4 Alert Reviewer window up, the holdings queue behind any S4 GO
REM  review (never on the same tabs at once), ~90 s each. Without it, they run here.
REM  Summary: reports\portfolio_review\Portfolio_Review_YYYYMMDD.md; each review is
REM  also a row in the Reviewer Log (source "portfolio").
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" portfolio_review.py %*
echo.
pause
endlocal

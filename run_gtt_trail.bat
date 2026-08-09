@echo off
REM Daily Chandelier trail of the live Dhan GTT stop legs (tighten-only).
REM Windows Task Scheduler entry point — mirrors run_journal_sync.bat.
REM
REM WHY THIS EXISTS: the trail was registered as an APScheduler job inside
REM scheduler_daemon.py at 15:45 IST. That daemon only runs while it is up, and
REM it is restarted constantly alongside Web Commander — so the job fired
REM exactly ONCE (24-Jul-2026) and never again. Meanwhile the broker stops sat
REM frozen at their entry levels for three weeks: SAILIFE 16.9% below its
REM Chandelier, NETWEB 11.4%, LAURUSLABS 7.4%. That is give-back that was
REM already earned.
REM
REM Task Scheduler owns this instead, for the same reason the journal sync does:
REM it survives restarts and catches up if the machine was off.
REM
REM 15:45 IST, Mon-Fri — just after the 15:30 close, so the Chandelier reads a
REM COMPLETED daily bar. --yes skips the interactive prompt; without it the run
REM raises EOFError headless AFTER printing its proposals, which is what made
REM the failure look like silence.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo ---------- %DATE% %TIME% ---------->> "logs\gtt_shield.log"
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" gtt_auto_shield.py --trail --yes >> "logs\gtt_shield.log" 2>&1

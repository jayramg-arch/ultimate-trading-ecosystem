@echo off
REM Start TradingView Desktop with the CDP remote-debugging port enabled so the
REM TradingView MCP / Claude can connect. Use this instead of the taskbar icon.
REM Pin this .bat to your taskbar / Start for a one-click "TV with debugging".
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_tradingview_cdp.ps1" %*

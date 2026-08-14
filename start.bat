@echo off
chcp 65001 >nul 2>&1
title Kiro Bot — Account Creator

echo ============================================================
echo   Kiro Builder ID — Self-Improving Anti-Ban Bot
echo   Direct launcher (no Docker, no swarm)
echo ============================================================
echo.

REM Use the Python from your PATH (Python 3.12)
set PYTHON=python

REM Run with panels.json (multi-panel mode)
%PYTHON% run_bot.py --panels panels.json --count 99999 --headless --no-proxy --mail-provider fake_legal --domain fake.legal --country us

echo.
echo [*] Bot finished. Press any key to exit...
pause >nul

@echo off
chcp 65001 >nul 2>&1
title Kiro Bot — 40 Worker Swarm

echo ============================================================
echo   Kiro Builder ID — 40 Concurrent Workers (Windows)
echo   No Docker. Just double-click start.bat
echo ============================================================
echo.

python launcher.py

echo.
echo [*] Press any key to exit...
pause >nul

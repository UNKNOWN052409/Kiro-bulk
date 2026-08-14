@echo off
REM Kiro Bot Swarm — Windows launcher
REM Usage: swarm.bat [--dry-run] [--instances N]

python "%~dp0swarm.py" %*
if errorlevel 1 (
    echo.
    echo Make sure Python 3 is installed and in PATH.
    echo Install deps: pip install -r requirements.txt
    echo Then: python swarm.py
)

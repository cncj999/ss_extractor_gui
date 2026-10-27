@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo Python not found. Please install Python 3.9+ and add it to PATH.
        echo Then double-click this file again.
        pause
        exit /b 1
    )
    py -3 ss_extractor_gui.py
    exit /b %ERRORLEVEL%
)

python ss_extractor_gui.py

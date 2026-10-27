@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo Python was not found. Please install Python 3.9+ and add it to PATH.
        pause
        exit /b 1
    )
    py -3 -m pip install --upgrade pip pyinstaller
    py -3 -m PyInstaller --noconsole --onefile --name "SSNodeExtractor" --hidden-import yaml --hidden-import pyaes --hidden-import requests --hidden-import pyperclip --add-data "config.example.yaml;." ss_extractor_gui.py
    echo.
    echo Build complete.
    echo Output is in the dist folder.
    pause
    exit /b 0
)

python -m pip install --upgrade pip pyinstaller
python -m PyInstaller --noconsole --onefile --name "SSNodeExtractor" --hidden-import yaml --hidden-import pyaes --hidden-import requests --hidden-import pyperclip --add-data "config.example.yaml;." ss_extractor_gui.py

echo.
echo Build complete.
echo Output is in the dist folder.
pause

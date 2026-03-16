@echo off
:: Always run from the folder where this .bat file lives
cd /d "%~dp0"
title NetDog Builder

echo.
echo  NetDog EXE Builder
echo  ==================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from https://www.python.org/downloads/
    echo          Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

:: Install / upgrade required packages
echo  Installing dependencies...
pip install --quiet --upgrade pyinstaller psutil requests pillow
if errorlevel 1 (
    echo  [ERROR] pip install failed.
    pause
    exit /b 1
)
echo  Dependencies OK.
echo.

:: Clean previous build
echo  Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo  Clean done.
echo.

:: Build
echo  Building NetDog.exe ...
echo.
pyinstaller NetDog.spec
if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed. Check the output above for details.
    pause
    exit /b 1
)

echo.
echo  ==================
echo  Build complete!
echo  EXE is at:  dist\NetDog.exe
echo  ==================
echo.
pause

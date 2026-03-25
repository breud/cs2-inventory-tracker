@echo off
echo ============================================
echo  CS2 Inventory Tracker - EXE Builder
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install it from https://python.org
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install requests flask pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Building EXE (this may take 30-60 seconds)...
pyinstaller --onefile --windowed ^
    --name "CS2InventoryTracker" ^
    --add-data "ui;ui" ^
    --icon "ui\icon.ico" ^
    cs2_tracker.py

if errorlevel 1 (
    echo ERROR: Build failed. See output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo Your EXE is at:  dist\CS2InventoryTracker.exe
echo.
pause

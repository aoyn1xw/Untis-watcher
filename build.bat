@echo off
REM Quick build script for Untis Watcher

echo ========================================
echo Building Untis Watcher Executable
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Run the build script
python build_exe.py

pause

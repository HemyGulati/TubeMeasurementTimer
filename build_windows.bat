@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Build TubeMeasurementTimer

echo.
echo ==========================================
echo   Building TubeMeasurementTimer.exe
echo ==========================================
echo.

REM Move to this script's folder
cd /d "%~dp0"

REM Find Python
set "PY_CMD="
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.10+ and tick "Add Python to PATH".
    pause
    exit /b 1
)

echo [INFO] Using Python command: %PY_CMD%
echo.

REM Upgrade pip and install build dependency
echo [INFO] Installing / updating PyInstaller...
call %PY_CMD% -m pip install --upgrade pip pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

echo.
echo [INFO] Cleaning old build folders...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "TubeMeasurementTimer.spec" del /f /q "TubeMeasurementTimer.spec"

echo.
echo [INFO] Building standalone one-file EXE...

if exist "assets\icon.ico" (
    call %PY_CMD% -m PyInstaller ^
        --noconfirm ^
        --clean ^
        --onefile ^
        --windowed ^
        --name "TubeMeasurementTimer" ^
        --icon "assets\icon.ico" ^
        --add-data "assets;assets" ^
        main.py
) else (
    echo [WARN] assets\icon.ico not found. Building without icon.
    call %PY_CMD% -m PyInstaller ^
        --noconfirm ^
        --clean ^
        --onefile ^
        --windowed ^
        --name "TubeMeasurementTimer" ^
        --add-data "assets;assets" ^
        main.py
)

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Build complete.
echo Output:
echo   %cd%\dist\TubeMeasurementTimer.exe
echo.
echo You can now upload this EXE to your GitHub Release.
echo.

pause
endlocal

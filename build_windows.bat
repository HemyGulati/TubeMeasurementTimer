@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo Building TubeMeasurementTimer.exe
echo ========================================

echo.
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo Python was not found in PATH.
        echo Please install Python 3.10+ and tick "Add Python to PATH".
        pause
        exit /b 1
    )
)

echo Using: %PY_CMD%
%PY_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :fail

%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :fail

if exist build rd /s /q build
if exist dist rd /s /q dist
if exist TubeMeasurementTimer.spec del /q TubeMeasurementTimer.spec

set "ICON_ARG="
if exist assets\icon.ico set "ICON_ARG=--icon assets\icon.ico"

%PY_CMD% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name TubeMeasurementTimer ^
  %ICON_ARG% ^
  main.py
if errorlevel 1 goto :fail

echo.
echo Build complete.
echo Output: dist\TubeMeasurementTimer.exe
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1

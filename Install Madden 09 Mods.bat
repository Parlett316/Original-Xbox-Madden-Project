@echo off
rem Opens the Madden NFL 09 mod installer (tools\installer.py).
rem The first time, it installs the Python packages the mods need.
cd /d "%~dp0"
title Madden NFL 09 mod installer
set "PY="
py -3 -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=python"
if defined PY goto :have_python

echo.
echo  This needs Python 3.10 or newer, which is free.
echo.
choice /c YN /m " Install Python now"
if errorlevel 2 goto :manual
winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto :manual
echo.
echo  Python is installed. Close this window and double-click this file again.
pause
exit /b 0

:manual
echo.
echo  Get Python from https://www.python.org/downloads/ and run its installer.
echo  Tick "Add python.exe to PATH" on its first screen.
echo  Then double-click this file again.
pause
exit /b 1

:have_python
echo  Checking the Python packages (the first time takes a minute)...
%PY% -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo  Could not install the packages in requirements.txt. Check the internet connection and try again.
  pause
  exit /b 1
)
echo  Opening the installer. Leave this window open while it runs.
%PY% tools\installer.py
if errorlevel 1 pause

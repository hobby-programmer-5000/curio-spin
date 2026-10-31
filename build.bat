@echo off
rem Builds the single-file executable dist\CurioSpin.exe.
rem First time only: uv venv --python 3.14 .venv ^&^& uv pip install --python .venv\Scripts\python.exe pyinstaller
cd /d "%~dp0"
.venv\Scripts\python.exe -X utf8 test_core.py || exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name CurioSpin --exclude-module unittest --exclude-module pydoc app.py

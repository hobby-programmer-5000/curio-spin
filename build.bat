@echo off
rem Builds the single-file executable dist\CurioSpin.exe.
rem First time only: uv venv --python 3.14 .venv ^&^& uv pip install --python .venv\Scripts\python.exe pyinstaller
rem
rem The excluded modules are standard-library parts CurioSpin never uses (networking, TLS, hashing,
rem compression, decimal). Leaving them out keeps OpenSSL, bzip2, zstd, xz and mpdecimal out of the exe.
rem See THIRD-PARTY-NOTICES.md for what is still bundled.
cd /d "%~dp0"
.venv\Scripts\python.exe -X utf8 test_core.py || exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name CurioSpin ^
  --exclude-module unittest --exclude-module pydoc ^
  --exclude-module ssl --exclude-module _ssl --exclude-module hashlib --exclude-module _hashlib ^
  --exclude-module socket --exclude-module _socket --exclude-module select ^
  --exclude-module bz2 --exclude-module _bz2 --exclude-module lzma --exclude-module _lzma ^
  --exclude-module compression.zstd --exclude-module _zstd ^
  --exclude-module decimal --exclude-module _decimal --exclude-module _pydecimal ^
  app.py

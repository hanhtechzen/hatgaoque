@echo off
rem One-click setup: create virtualenv, install packages, create .env
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Chua co Python. Tai Python 3.12 tro len tai https://www.python.org/downloads/
  echo     Khi cai nho tick "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  echo === Tao moi truong Python (.venv) ===
  python -m venv .venv || goto :err
)
echo === Cai thu vien (lan dau mat vai phut) ===
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
if not exist .env (
  copy .env.example .env >nul
  echo === Da tao file .env - mo trang quan ly, vao Cai dat de dan key ===
)
if not exist logs mkdir logs
echo.
echo === XONG! Nhap dup start_web.bat de mo trang quan ly ===
pause
exit /b 0
:err
echo [!] Cai dat loi - xem thong bao phia tren.
pause
exit /b 1

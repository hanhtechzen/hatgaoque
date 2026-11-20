@echo off
rem Open the Hat Gao Que Studio web manager (http://127.0.0.1:8686)
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m studio web %*
if "%~1"=="" pause

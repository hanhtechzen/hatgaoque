@echo off
rem Daily job for Task Scheduler: make video(s), schedule Facebook posts, sync stats/comments, weekly compilation
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m studio run >> "logs\task.log" 2>&1
".venv\Scripts\python.exe" -m studio sync >> "logs\task.log" 2>&1
".venv\Scripts\python.exe" -m studio weekly >> "logs\task.log" 2>&1

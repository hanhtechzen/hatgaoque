@echo off
rem Install GPU (NVIDIA) extras: CUDA torch + diffusers. Run setup.bat first.
cd /d "%~dp0"
if not exist .venv (
  echo [!] Chay setup.bat truoc.
  pause
  exit /b 1
)
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo [!] Khong thay nvidia-smi. Cai driver NVIDIA moi nhat: https://www.nvidia.com/Download/index.aspx
  pause
  exit /b 1
)
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
echo === Cai PyTorch ban CUDA (khoang 3 GB) ===
".venv\Scripts\python.exe" -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu128 || goto :err
echo === Cai thu vien AI (diffusers...) ===
".venv\Scripts\python.exe" -m pip install -r requirements-gpu.txt || goto :err
echo.
echo === Kiem tra GPU va tao thu 1 anh + 1 clip (lan dau tai model ~20-30 GB, co the mat 30-60 phut) ===
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m studio gpu-test
echo.
echo === XONG. Xem ket qua trong output\gpu_test ===
pause
exit /b 0
:err
echo [!] Cai dat loi - xem thong bao phia tren.
pause
exit /b 1

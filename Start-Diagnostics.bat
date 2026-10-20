@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0diagnose.py" --open-report
  goto :finish
)
python -c "import sys; raise SystemExit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 (
  python "%~dp0diagnose.py" --open-report
  goto :finish
)
echo 需要 Python 3.8 或更新版本。
echo 请从 https://www.python.org/downloads/windows/ 安装 Python 3，并启用 Add python.exe to PATH。
echo 安装完成后，重新双击这个诊断文件。
echo 本工具不会自动安装软件，也不需要管理员权限。
choice /C YN /N /M "Open the official Python download page? [Y/N]: "
if errorlevel 2 goto :finish
start "" "https://www.python.org/downloads/windows/"
:finish
echo.
echo 按任意键关闭窗口。
pause >nul
endlocal

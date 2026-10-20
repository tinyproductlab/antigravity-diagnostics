@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0diagnose.py"
  goto :finish
)
python -c "import sys; raise SystemExit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 (
  python "%~dp0diagnose.py"
  goto :finish
)
echo 需要 Python 3.8 或更新版本。
echo 请从 https://www.python.org/downloads/windows/ 安装 Python 3，并启用 Add python.exe to PATH。
echo 本工具不会自动下载安装程序，也不需要管理员权限。
:finish
echo.
echo 按任意键关闭窗口。
pause >nul
endlocal

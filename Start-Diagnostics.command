#!/bin/zsh
cd -- "${0:A:h}" || exit 1
export PYTHONIOENCODING=utf-8
if ! command -v python3 >/dev/null 2>&1; then
  print '需要 Python 3。请从 https://www.python.org/downloads/macos/ 安装后再运行。'
else
  python3 ./diagnose.py
fi
print '\n按回车关闭窗口。'
read -r

#!/bin/zsh
cd -- "${0:A:h}" || exit 1
export PYTHONIOENCODING=utf-8
print 'Antigravity 诊断助手：先检查环境，再给出具体处理步骤。'
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
  python3 ./start.py
else
  print '\n未检测到可用的 Python 3.8+，诊断尚未开始。'
  print '1. 从 Python 官方网站下载适合 macOS 的安装包。'
  print '2. 双击下载的 .pkg，按照安装向导完成安装。'
  print '3. 安装完成后，重新双击这个诊断文件。无需运行其他命令。'
  print '\n是否现在打开官方下载页？输入 y 并回车：'
  read -r answer
  if [[ "$answer" == [yY] ]]; then
    open 'https://www.python.org/downloads/macos/'
  fi
fi
print '\n按回车关闭窗口。'
read -r

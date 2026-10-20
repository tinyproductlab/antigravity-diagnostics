"""Desktop entry point, with a terminal fallback when Tk is unavailable."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from diagnose import log_paths
from live_test import capture
import json


def launch_antigravity():
    if sys.platform=='darwin':
        return subprocess.run(['open','-a','Antigravity'],capture_output=True).returncode==0
    if sys.platform=='win32':
        paths=[Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Programs/Antigravity/Antigravity.exe',
               Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Antigravity/Antigravity.exe',
               Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Antigravity/Antigravity.exe']
        for path in paths:
            if path.is_file():
                subprocess.Popen([str(path)])
                return True
    return False


def terminal():
    print('当前 Python 缺少可用的新版图形界面组件，使用相同的终端登录测试流程。')
    input('按回车开始登录测试（先记录日志起点，再打开 Antigravity）：')
    snapshot=capture(list(log_paths(Path.home())))
    launch_antigravity()
    print('请在 Antigravity 点击登录，完成浏览器授权。遇到失败或成功后回到这里。')
    input('已重试登录后，按回车查看本次测试结果：')
    with tempfile.TemporaryDirectory(prefix='antigravity-test-') as folder:
        path=Path(folder)/'snapshot.json'
        path.write_text(json.dumps(snapshot),encoding='utf-8')
        return subprocess.call([sys.executable,str(Path(__file__).with_name('diagnose.py')),'--snapshot',str(path),'--open-report'])


def main():
    try:
        import tkinter
        from gui import run
        if tkinter.TkVersion < 8.6:
            return terminal()
    except ImportError:
        return terminal()
    try:
        return run()
    except tkinter.TclError:
        return terminal()

if __name__=='__main__':
    try:sys.exit(main() or 0)
    except KeyboardInterrupt:print('\n已取消。')

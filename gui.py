"""Local Tk interface. All logs stay on this computer."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from diagnose import analyze, log_paths, FAQ, ACTION_STEPS
from live_test import capture, fresh_tail


def run():
    root=tk.Tk()
    root.title('Antigravity 登录测试与诊断助手')
    root.geometry('800x680')
    root.minsize(620,520)
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='先重试登录，再定位这次的问题',font=('',19,'bold')).pack(anchor='w')
    ttk.Label(frame,text='1. 开始测试  →  2. 到 Antigravity 点击登录  →  3. 返回查看结果',wraplength=720).pack(anchor='w',pady=(12,8))
    ttk.Label(frame,text='只分析本次新增日志。账号授权、扫码及其他验证由你本人完成。',wraplength=720).pack(anchor='w')
    status=tk.StringVar(value='点击“开始登录测试”。工具会记录日志起点并尝试打开 Antigravity。')
    ttk.Label(frame,textvariable=status,wraplength=720).pack(anchor='w',pady=16)
    controls=ttk.Frame(frame);controls.pack(fill='x')
    actions=ttk.Frame(frame)
    text=tk.Text(frame,wrap='word',height=18,font=('',12))
    state={'snapshot':None,'running':False,'closed':False,'url':None,'seen':set(),'folder':None}

    def append(value):
        text.insert('end',value+'\n');text.see('end')

    def scan():
        active=[];success=False;urls=[]
        for path in log_paths(Path.home()):
            try:
                fresh=fresh_tail(path,state['snapshot'])
                a,_,ok,u=analyze(fresh)
                active.extend(a);success=success or ok;urls.extend(u)
            except (OSError,ValueError):pass
        return active,success,urls

    def monitor():
        if state['closed'] or state['snapshot'] is None:return
        if not state['running']:
            active,success,urls=scan()
            if urls:state['url']=urls[-1]
            for key,title,_ in active:
                if key not in state['seen']:
                    state['seen'].add(key);append('发现本次日志线索：'+title)
            if active:
                status.set('已发现本次错误线索。完成这次登录尝试后，点击“查看本次结果”。')
            elif success:
                status.set('本次日志出现登录成功事件。请确认应用界面，并点击“查看本次结果”。')
        root.after(2500,monitor)

    def begin():
        from start import launch_antigravity
        state['snapshot']=capture(list(log_paths(Path.home())))
        state['seen']=set();state['url']=None
        for child in actions.winfo_children():child.destroy()
        text.delete('1.0','end')
        append('测试已开始，只读取此刻之后写入的日志。')
        opened=launch_antigravity()
        append('请在 Antigravity 点击 Continue with Google，完成浏览器授权。')
        if not opened:append('未找到应用启动入口，请从开始菜单或应用程序文件夹手动打开 Antigravity。')
        append('遇到失败、卡住或成功后，回到此窗口点击“查看本次结果”。')
        status.set('正在等待你重试登录。工具不会替你选择账号或提交验证。')
        result_button.config(state='normal')
        begin_button.config(text='重新开始测试')
        if not state.get('monitor_started'):
            state['monitor_started']=True;root.after(2500,monitor)

    def done(report,active,urls,error):
        if state['closed']:return
        state['running']=False;begin_button.config(state='normal');result_button.config(state='normal')
        if error:
            status.set('诊断未完成：'+error);return
        text.delete('1.0','end');append(report.read_text(encoding='utf-8'))
        status.set('本次结果已生成。按“现在该怎么做”处理；完成后可重新开始测试验证。')
        for child in actions.winfo_children():child.destroy()
        button_count=[0]
        def button(label,callback):
            i=button_count[0];button_count[0]+=1
            ttk.Button(actions,text=label,command=callback).grid(row=i//3,column=i%3,sticky='w',padx=(0,8),pady=4)
        def link(label,url):button(label,lambda:webbrowser.open(url))
        if urls:link('打开账号验证',urls[-1])
        keys={x[0] for x in active}
        if 'region' in keys:
            button('关联地区处理步骤',lambda:messagebox.showinfo('关联地区处理步骤','\n\n'.join(str(i)+'. '+step for i,step in enumerate(ACTION_STEPS['region'][1],1))))
            link('核对关联地区','https://policies.google.com/terms')
            link('官方支持范围',FAQ+'#what-is-google-antigravitys-geographical-availability')
            link('申请更正关联地区','https://policies.google.com/country-association-form')
        if 'age' in keys:link('年龄验证说明',FAQ+'#why-is-my-age-unverified')
        link('模型权益','https://www.antigravity.google/docs/models/')
        link('官方支持','https://antigravity.google/support')
        button('打开报告',lambda:open_result(report))

    def open_result(path):
        from diagnose import open_report
        try:open_report(path)
        except OSError:messagebox.showinfo('报告位置',str(path))

    def results():
        if state['snapshot'] is None:return
        state['running']=True;begin_button.config(state='disabled');result_button.config(state='disabled')
        status.set('正在分析本次日志并检查连通性，请稍候……')
        active,_,urls=scan()
        report=Path(__file__).resolve().parent/('诊断报告-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.txt')
        # Background work posts data to a queue; Tk APIs only run on the UI thread.
        import queue
        output=queue.Queue()
        def work():
            try:
                with tempfile.TemporaryDirectory(prefix='antigravity-test-') as folder:
                    snapshot=Path(folder)/'snapshot.json'
                    snapshot.write_text(json.dumps(state['snapshot']),encoding='utf-8')
                    r=subprocess.run([sys.executable,str(Path(__file__).with_name('diagnose.py')),'--snapshot',str(snapshot),'--output',str(report)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
                output.put(None if r.returncode==0 and report.is_file() else '请从终端运行 diagnose.py 查看详细信息。')
            except OSError:output.put('无法启动本机诊断进程。')
        def poll():
            try:error=output.get_nowait()
            except queue.Empty:
                root.after(200,poll);return
            done(report,active,urls,error)
        threading.Thread(target=work,daemon=True).start();root.after(200,poll)

    begin_button=ttk.Button(controls,text='开始登录测试',command=begin);begin_button.pack(side='left',padx=(0,10))
    result_button=ttk.Button(controls,text='查看本次结果',command=results,state='disabled');result_button.pack(side='left')
    actions.pack(fill='x',pady=(12,4));text.pack(fill='both',expand=True,pady=8)
    append('尚未开始测试。不会使用旧日志直接判断你现在的登录结果。')
    def close():state['closed']=True;root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    root.mainloop()

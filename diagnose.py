#!/usr/bin/env python3
"""Read-only Antigravity diagnostics. Standard library only; never reads tokens."""
import argparse
import concurrent.futures
import datetime as dt
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

FAQ = 'https://www.antigravity.google/docs/faq/'
RULES = [
 ('validation', r'VALIDATION_REQUIRED|Verify your account to continue|Further action is required', 'Google 要求额外账号验证', '在本次错误附近查找 validation_url，打开 Google 官方验证页并由本人完成验证；随后重新登录。'),
 ('region', r'UNSUPPORTED_LOCATION|User location is not supported|not available in your (?:country|region)|location is not supported for the API', '服务端报告地区不受支持', '核对官方支持地区和 Google 条款页显示的账号关联地区。如关联地区有误，通过 Google 官方渠道申请更正；实际所在地不受支持时，脚本不能解除限制。'),
 ('age', r'AGE_RESTRICTED|AGE_VERIFICATION_REQUIRED|age.{0,25}(?:unverified|verification required)|under (?:the age of )?18', '年龄或年龄验证限制', '达到服务年龄要求后，通过 Google 账号官方页面完成年龄验证；未满足年龄要求不能用脚本解锁。'),
 ('expired', r'invalid_grant|token.{0,15}expired|UNAUTHENTICATED|invalid authentication credentials', '凭据过期或无效', '先在应用正常退出账号，再重新登录正确的 Google 账号。不要公开 token，也不要直接删除整个配置目录。'),
 ('quota', r'RESOURCE_EXHAUSTED|quota.{0,30}exceeded|rate.?limit.{0,20}exceeded', '配额或请求速率受限', '查看应用用量及重置时间。稍后重试；若付费方案未识别，核对登录账号和订阅归属。配额错误不等于登录失败。'),
 ('billing', r'BILLING_DISABLED|billing account.{0,30}(?:disabled|not found)|LICENSE_NOT_FOUND|license.{0,25}(?:missing|expired)', '计费或企业许可证异常', '个人账号检查订阅；企业账号请管理员检查项目、计费状态及许可证。不要为了排查直接开通付费项目。'),
 ('tls', r'CERTIFICATE_VERIFY_FAILED|CERT_AUTHORITY_INVALID|x509:|certificate (?:verify failed|has expired|is not trusted)|TLS handshake timeout', '证书或 TLS 连接异常', '检查系统时间、代理证书和企业网络策略。不要关闭证书校验；企业网络请联系管理员。'),
 ('dns', r'ENOTFOUND|no such host|name resolution|ERR_NAME_NOT_RESOLVED', '域名解析失败', '检查 DNS 和网络/代理日志，确认 Google 相关域名能解析。TUN 模式可能使用合成地址，单看地址不能判定异常。'),
 ('network', r'ERR_PROXY_CONNECTION_FAILED|proxyconnect|connection refused|ERR_CONNECTION_RESET|network is unreachable|i/o timeout|context deadline exceeded', '网络、代理或本地服务连接异常', '结合报错目标判断：localhost/127.0.0.1 通常是应用本地服务；外部 Google 域名则检查代理规则、TUN 和节点连通性。先保留日志，再重启应用验证。'),
 ('callback', r'redirect_uri_mismatch|invalid_state|state mismatch|OAuth.{0,30}callback.{0,25}(?:failed|error)', 'OAuth 回调异常', '从应用重新发起登录，只完成最新的一次授权。检查浏览器是否允许打开 Antigravity，以及 localhost 是否被错误代理。'),
 ('keyring', r'Failed to save token to keyring|keychain.{0,30}(?:denied|failed|locked)', '钥匙串访问异常', '检查 macOS 钥匙串是否解锁及应用授权。若同一行提示 falling back to file，代表已有文件回退，不能单凭此项认定登录失败。'),
 ('permission', r'PERMISSION_DENIED|HTTP[ /:]*(?:403)|"code"\s*:\s*403', '服务端权限拒绝（通用信号）', '403 不是地区限制的充分证据。优先看同一响应中的 reason、message 和更具体的验证/地区错误。企业用户检查 IAM 和许可证。'),
 ('crash', r'FATAL|panic:|uncaught exception|ERR_CONNECTION_REFUSED', '客户端或本地服务异常', '保存诊断报告后正常重启应用，并检查官方更新；若反复出现，向官方支持提供版本与错误时间。'),
]

def tail(path, size=2_000_000):
    with path.open('rb') as f:
        f.seek(0, 2)
        length = f.tell()
        f.seek(max(0, length-size))
        data = f.read()
    if length > size:
        data = data.partition(b'\n')[2]
    return data.decode('utf-8', errors='replace')

def safe_verification_urls(text):
    result = []
    for m in re.finditer(r'"validation_url"\s*:\s*"([^"\r\n]+)"', text):
        try:
            url = json_unescape(m.group(1))
            p = urllib.parse.urlsplit(url)
            if (p.scheme == 'https' and p.hostname == 'accounts.google.com'
                    and not p.username and not p.password and p.port in (None,443)
                    and p.path.startswith(('/signin/', '/v3/signin/'))):
                result.append(url)
        except (ValueError, TypeError):
            pass
    return list(dict.fromkeys(result))

def json_unescape(value):
    import json
    return json.loads('"'+value+'"')

def analyze(text):
    # The most recent explicit successful login supersedes earlier login failures
    # within this same log only. Never compare unrelated clients as one session.
    starts = list(re.finditer(r'Starting app \(v|Starting language server process', text))
    if starts:
        text = text[starts[-1].start():]
    successes = list(re.finditer(r'Auth succeeded|authentication (?:succeeded|successful)', text, re.I))
    cutoff = successes[-1].end() if successes else 0
    active, history = [], []
    for key, pattern, title, advice in RULES:
        hits = list(re.finditer(pattern, text, re.I))
        if not hits:
            continue
        item = (key, title, advice)
        (active if hits[-1].start() >= cutoff else history).append(item)
    # Generic 403 provides no independent diagnosis when a specific cause exists.
    if any(x[0] in ('validation','region','age','billing') for x in active):
        active = [x for x in active if x[0] != 'permission']
    urls = safe_verification_urls(text[cutoff:]) if any(x[0]=='validation' for x in active) else []
    return active, history, bool(successes), urls

def log_paths(home, platform=None, environ=None):
    platform = platform or sys.platform
    env = os.environ if environ is None else environ
    fixed = [home/'.gemini/antigravity-cli/cli.log', home/'.gemini/antigravity/cli.log']
    roots = []
    if platform == 'win32':
        roaming = Path(env.get('APPDATA') or home/'AppData/Roaming')
        local = Path(env.get('LOCALAPPDATA') or home/'AppData/Local')
        for base in (roaming/'Antigravity', local/'Antigravity'):
            fixed.extend([base/'logs/main.log', base/'logs/language_server.log',
                          base/'main.log', base/'language_server.log'])
            roots.append(base/'logs')
    else:
        fixed[0:0] = [home/'Library/Logs/Antigravity/main.log',
                      home/'Library/Logs/Antigravity/language_server.log']
        roots.append(home/'Library/Application Support/Antigravity/logs')
    paths = fixed[:]
    for base in (home/'.gemini/antigravity-cli/log',home/'.gemini/antigravity/log'):
        if base.is_dir() and not (base.parent/'cli.log').is_file():
            try:
                paths.extend(sorted(base.glob('*.log'),key=lambda p:p.stat().st_mtime,reverse=True)[:1])
            except OSError:
                pass
    # IDE logs live in session directories. Read only the newest session;
    # retain its extension/output logs rather than mixing old sessions.
    for root in roots:
        if not root.is_dir():
            continue
        try:
            sessions=[x for x in root.iterdir() if x.is_dir()]
            if sessions:
                session=max(sessions,key=lambda p:p.stat().st_mtime)
                paths.extend(sorted(session.rglob('*.log'),key=lambda p:p.stat().st_mtime,reverse=True)[:12])
        except OSError:
            pass
    seen=set()
    for p in paths:
        try:
            real=p.resolve()
            if real not in seen and p.is_file():
                seen.add(real)
                yield p
        except OSError:
            continue

def windows_proxy_summary(reader=None):
    # Never include proxy addresses, PAC URLs or registry contents in reports.
    if reader is None:
        def reader():
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                values={}
                for name in ('ProxyEnable','AutoConfigURL'):
                    try: values[name]=winreg.QueryValueEx(key,name)[0]
                    except OSError: pass
                return values
    try:
        values=reader()
        return ['Windows 用户代理：'+('已开启' if values.get('ProxyEnable') else '未检测到开启'),
                'PAC 自动配置：'+('已配置' if values.get('AutoConfigURL') else '未检测到配置'),
                '说明：WinHTTP、应用专用代理与 TUN 可能不同，不能据此判定应用是否经过代理。']
    except (OSError,ImportError):
        return ['Windows 用户代理设置无法读取；不能据此推断网络是否正常。']

def command(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''

def probe(host):
    try:
        req = urllib.request.Request('https://'+host+'/', method='HEAD')
        with urllib.request.urlopen(req, timeout=7) as response:
            return host, '收到 HTTPS 响应（HTTP %s）' % response.status
    except urllib.error.HTTPError as e:
        return host, '收到 HTTPS 响应（HTTP %s）；无凭据探测，不据此判断账号权限' % e.code
    except urllib.error.URLError as e:
        reason=e.reason
        if isinstance(reason, ssl.SSLCertVerificationError): label='证书校验失败'
        elif isinstance(reason, socket.gaierror): label='DNS 解析失败'
        elif isinstance(reason, (socket.timeout, TimeoutError)): label='连接超时'
        else: label='连接失败（需结合应用日志判断）'
        return host,label
    except (OSError, TimeoutError):
        return host,'连接失败或超时'


def main():
    parser=argparse.ArgumentParser(description='Antigravity 只读诊断：本地日志、网络及建议')
    parser.add_argument('--offline', action='store_true', help='不发起网络探测')
    parser.add_argument('--log', action='append', type=Path, help='额外日志，可重复指定')
    parser.add_argument('--output', type=Path, help='报告保存路径')
    args=parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    home=Path.home()
    lines=['Antigravity 登录与使用诊断报告',dt.datetime.now().astimezone().isoformat(timespec='seconds'),
           '', '检查方式：只读日志及网络状态；不读取账号凭据、不修改代理、不删除配置。',
           '报告不包含原始日志、邮箱、令牌、完整验证链接或公网 IP。','']
    if sys.platform == 'darwin':
        proxy=command(['scutil','--proxy'])
        explicit=bool(re.search(r'(?:HTTP|HTTPS|SOCKS)Enable\s*:\s*1',proxy))
        route=command(['route','-n','get','default'])
        tunnel=bool(re.search(r'interface:\s*utun',route))
        lines += ['网络设置：显式系统代理%s；默认路由%s。' %
                  ('已开启' if explicit else '未检测到开启', '经过隧道接口' if tunnel else '未检测到隧道接口'),
                  '说明：系统代理关闭不代表未走代理；隧道接口也不保证所有 Google 请求均经过同一路径。','']
    if sys.platform == 'win32':
        lines += windows_proxy_summary()+['']
    candidates=list(log_paths(home)) if not args.log else args.log
    urls=[]
    found=0
    for path in candidates:
        try:
            text=tail(path)
            active,history,success,new_urls=analyze(text)
            found+=1
            label=str(path).replace(str(home),'~')
            modified=dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone().strftime('%Y-%m-%d %H:%M:%S %z')
            lines += ['日志：'+label, '最后修改：'+modified]
            if (dt.datetime.now().timestamp()-path.stat().st_mtime)>86400:
                lines += ['注意：日志超过24小时未更新，不能代表刚才的尝试。']
            if success:
                lines += ['记录中存在登录成功事件；此前匹配到的错误列为历史。']
            if active:
                for key,title,advice in active:
                    if key == 'keyring' and sys.platform == 'win32':
                        advice='检查 Windows 凭据管理器或组织安全策略；若已回退到文件保存，不能单凭此项判断登录失败。'
                    lines += ['【待核实】'+title, '  依据：日志匹配到 '+key+' 类错误（最后成功事件之后，或尚无成功事件）。', '  办法：'+advice]
            else:
                lines += ['未发现匹配的待处理错误；不代表所有功能正常。']
            if history:
                lines += ['历史线索（可能已解决）：'+'、'.join(x[1] for x in history)]
            urls.extend(new_urls)
            lines += ['']
        except (OSError, ValueError):
            lines += ['某份日志无法读取，已跳过。']
    if not found:
        lines += ['未找到可读日志。请先在 Antigravity 重现一次失败，再重新运行。',
                  '仅安装桌面版时，CLI 日志可能不存在；本工具不会为诊断自动安装 CLI。','']
    if not args.offline:
        lines += ['HTTPS 连通性探测（不发送账号凭据，仅检查当前脚本的网络路径）：']
        hosts=['accounts.google.com','antigravity.google','cloudcode-pa.googleapis.com','daily-cloudcode-pa.googleapis.com']
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for host,status in pool.map(probe,hosts): lines += ['  '+host+'：'+status]
        lines += ['探测成功不代表账号有权益，也不能完全代表 Antigravity 进程的网络路径。','']
    lines += ['尚不能自动判定：账号真实关联地区、年龄、订阅类型、单个模型权益及服务端风控。',
              '缺少模型时，请核对正式付费/试用/合作伙伴赠送方案；脚本不能开通付费权益。',
              '地区/年龄/账号资格须以 Google 官方规则和账号页面为准。',
              '若仍无结论：先重现故障，再把本报告交给支持人员；不要公开完整日志。','',
              '官方资料：'+FAQ,'账号验证说明：https://support.google.com/accounts/answer/15437069',
              '模型资格：https://www.antigravity.google/docs/models/']
    report='\n'.join(lines)+'\n'
    destination=args.output or Path(__file__).resolve().parent/('诊断报告-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.txt')
    try:
        fd=os.open(str(destination),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(report)
    except OSError:
        print('报告无法写入指定目录；以下为诊断结果。')
        destination=None
    print(report)
    if destination: print('报告已保存：'+str(destination))
    urls=list(dict.fromkeys(urls))
    if urls and sys.stdin.isatty():
        print('\n发现 Google 官方验证入口。链接只在本机使用，不写入报告。')
        answer=input('是否打开最近找到的验证入口？输入 y 打开，其他键跳过：').strip().lower()
        if answer=='y':
            import webbrowser
            webbrowser.open(urls[-1])
            print('请本人完成验证，再回应用重新登录；旧链接若失效，请重现失败后重跑诊断。')

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\n已取消。')

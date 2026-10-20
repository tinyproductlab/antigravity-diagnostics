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


ACTION_STEPS = {
 'validation': ('完成 Google 额外账号验证', [
   '选择下方“打开账号验证入口”，按网页要求用手机扫码或完成设备验证。',
   '看到验证成功后，回到 Antigravity，从应用重新发起登录。',
   '若仍停在欢迎页，刷新应用窗口；等待几分钟同步后再试。旧链接失效时先重现错误，再运行本工具。']),
 'region': ('核对地区资格', [
   '打开 Google 条款页，查看页面底部显示的账号关联国家/地区。',
   '打开官方支持地区列表，核对实际所在地是否支持。节点名字或网页能打开不能证明资格正常。',
   '关联地区确有错误时，通过 Google 官方渠道申请更正；所在地暂不支持时，脚本不能解除限制。']),
 'age': ('完成官方年龄核验', [
   '打开官方 FAQ 的年龄说明，进入其中的年龄验证入口。',
   '仅在满足年龄要求时按 Google 提示完成验证，然后重新登录。不要反复更改生日。']),
 'expired': ('刷新登录凭据', [
   '在 Antigravity 的账号菜单正常退出登录。',
   '从应用重新发起登录，选择订阅对应的 Google 账号，只完成最新的一次授权。',
   '若反复提示 invalid_grant，核对电脑日期与时间是否自动同步，再重试。']),
 'quota': ('处理配额限制', [
   '在 Antigravity 的用量页面查看剩余额度和重置时间。',
   '等待额度重置，或选择账号实际可用且还有额度的模型。',
   '付费权益未识别时核对订阅账号；不要通过反复登录或删除配置尝试增加额度。']),
 'billing': ('检查企业许可证或计费', [
   '个人用户：核对登录账号与订阅所属账号是否一致。',
   '企业用户：将本报告交给管理员，检查项目 IAM、许可证、计费账户和组织限制。']),
 'tls': ('修复证书连接条件', [
   '检查系统日期与时间是否正确，并开启自动同步。',
   '若使用企业网络或 HTTPS 检查代理，请管理员配置可信证书链。',
   '随后重新登录并重跑检测；不要关闭证书校验。']),
 'dns': ('检查域名解析', [
   '在浏览器打开 Google 登录页，确认当前网络可访问。',
   '在正在使用的代理软件中查看 Google 域名的 DNS 与连接日志；TUN 合成地址本身不等于故障。',
   '若为企业网络，将 DNS 错误和报错时间交给管理员；修正网络配置后重试。']),
 'network': ('定位网络或本地服务故障', [
   '先核对报错目标：localhost/127.0.0.1 指向应用本地服务，正常退出并重新打开应用后再试。',
   '若是外部 Google 域名，检查当前代理的连接记录，确认 Antigravity 进程有请求与响应。',
   '查看下方连通性结果；若只有浏览器可用，请检查应用代理路径。修正配置后重新登录并重跑检测。']),
 'callback': ('重新建立浏览器授权回调', [
   '从 Antigravity 重新点击登录，完成刚打开的最新授权页面。',
   '浏览器询问是否打开 Antigravity 时允许本次打开。',
   '若回调目标为 localhost，检查本地回环地址是否被代理或防火墙错误拦截。']),
 'keyring': ('检查凭据保存状态', [
   'Mac 检查“钥匙串访问”是否解锁；Windows 检查凭据管理器和组织策略。',
   '若日志同时提示 falling back to file，说明已有回退保存；优先处理其他明确错误。']),
 'permission': ('查清具体拒绝原因', [
   '通用 403 无法直接确定地区问题。查看报告是否同时有账号验证、年龄、地区或许可证信号。',
   '个人用户确认是自己的正确 Google 账号；企业用户请管理员核对 IAM 与组织策略。',
   '仍无具体原因时，将本次故障时间与本报告发给官方支持。']),
 'crash': ('恢复本地客户端', [
   '保存正在进行的工作，正常退出并重新打开 Antigravity。',
   '检查官方更新，再重现一次问题并运行本工具。不要先删除整个账号或配置目录。']),
}

def next_steps(keys, found, network_failed=False):
    keys=list(dict.fromkeys(keys))
    if network_failed and not any(k in keys for k in ('network','dns','tls')):
        keys.append('network')
    if not keys:
        return ['现在该怎么做',
                '尚无足够证据确定当前根因。'+('本机未找到日志。' if not found else '已读日志未匹配到当前错误。'),
                '1. 保持工具所在文件夹打开，在 Antigravity 重现一次失败。',
                '2. 立即重新双击运行，再核对报告里的日志更新时间是否对应本次失败。',
                '3. 若只是缺少模型，选择“查看模型权益说明”，核对付费/试用/赠送方案及订阅账号。',
                '4. 仍无法定位时，选择“打开官方支持入口”，提供故障发生时间、本报告和界面截图。','']
    out=['现在该怎么做（按日志线索给出的操作顺序）']
    for key in ACTION_STEPS:
        if key not in keys: continue
        title,steps=ACTION_STEPS[key]
        out.append('【'+title+'】')
        out.extend(str(i)+'. '+step for i,step in enumerate(steps,1))
        out.append('')
    return out

def offer_actions(keys, urls, destination):
    import webbrowser
    actions=[]
    if urls: actions.append(('打开账号验证入口（可能需本人手机扫码）',urls[-1]))
    if 'region' in keys:
        actions.extend([('查看 Google 账号关联地区','https://policies.google.com/terms'),
                        ('查看官方支持地区',FAQ+'#what-is-google-antigravitys-geographical-availability')])
    if 'age' in keys: actions.append(('查看官方年龄验证说明',FAQ+'#why-is-my-age-unverified'))
    actions.extend([('查看模型权益说明','https://www.antigravity.google/docs/models/'),
                    ('打开官方支持入口','https://antigravity.google/support')])
    while True:
        print('\n下一步操作（只打开你选择的页面，不改变账号设置）：')
        for i,(title,_) in enumerate(actions,1):print('  '+str(i)+'. '+title)
        print('  0. 完成并退出')
        answer=input('请输入数字并回车：').strip()
        if answer=='0' or not answer:return
        if answer.isdigit() and 1<=int(answer)<=len(actions):
            opened=webbrowser.open(actions[int(answer)-1][1])
            print('已请求浏览器打开。完成页面操作后，请回到应用重新登录并重跑诊断。' if opened else '浏览器未能自动打开；请按报告中的官方资料入口继续。')
        else:print('请输入列表中的数字。')

def open_report(path):
    if sys.platform=='darwin':subprocess.run(['open',str(path)],check=False)
    elif sys.platform=='win32':os.startfile(str(path))


def main():
    parser=argparse.ArgumentParser(description='Antigravity 只读诊断：本地日志、网络及建议')
    parser.add_argument('--open-report', action='store_true', help='诊断后打开本地中文报告')
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
    all_keys=[]
    network_failed=False
    found=0
    for path in candidates:
        try:
            text=tail(path)
            active,history,success,new_urls=analyze(text)
            found+=1
            if dt.datetime.now().timestamp()-path.stat().st_mtime <= 86400:
                all_keys.extend(x[0] for x in active)
            else:
                new_urls=[]
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
            for host,status in pool.map(probe,hosts):
                lines += ['  '+host+'：'+status]
                if '收到 HTTPS 响应' not in status: network_failed=True
        lines += ['探测成功不代表账号有权益，也不能完全代表 Antigravity 进程的网络路径。','']
    lines += ['尚不能自动判定：账号真实关联地区、年龄、订阅类型、单个模型权益及服务端风控。',
              '缺少模型时，请核对正式付费/试用/合作伙伴赠送方案；脚本不能开通付费权益。',
              '地区/年龄/账号资格须以 Google 官方规则和账号页面为准。',
              '若仍无结论：先重现故障，再把本报告交给支持人员；不要公开完整日志。','',
              '官方资料：'+FAQ,'账号验证说明：https://support.google.com/accounts/answer/15437069',
              '模型资格：https://www.antigravity.google/docs/models/']
    plan=next_steps(all_keys,found,network_failed)
    lines=lines[:6]+['']+plan+['详细检查结果']+lines[6:]
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
    if destination and args.open_report:
        try: open_report(destination)
        except OSError: print('报告未能自动打开，请到上述路径手动查看。')
    if sys.stdin.isatty():
        offer_actions(all_keys,list(dict.fromkeys(urls)),destination)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\n已取消。')

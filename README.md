# Antigravity 诊断助手

[官网下载页](https://tinylabpro.com/downloads/antigravity/) · [GitHub 下载](https://github.com/tinyproductlab/antigravity-diagnostics/releases/latest)

面向普通用户的本地只读诊断脚本：检查 Antigravity 登录或使用错误，输出中文诊断线索与处理建议。

## 下载及使用

| 系统 | 下载 | 解压后运行 |
| --- | --- | --- |
| macOS | [Mac ZIP](https://github.com/tinyproductlab/antigravity-diagnostics/releases/latest/download/antigravity-diagnostics-macos.zip) | `Start-Diagnostics.command` |
| Windows | [Windows ZIP](https://github.com/tinyproductlab/antigravity-diagnostics/releases/latest/download/antigravity-diagnostics-windows.zip) | `Start-Diagnostics.bat` |

1. 安装 **Python 3.8 或更新版本**，下载地址为 [python.org](https://www.python.org/downloads/)。Windows 安装时启用 Add python.exe to PATH。
2. **完整解压**下载包，双击对应启动文件打开工具。
3. 点击 **开始登录测试**。工具记录当前日志位置并尝试打开 Antigravity；未找到启动入口时请手动打开。
4. 在 Antigravity 点击登录，完成你自己的账号授权。失败、卡住或成功后回到工具。
5. 点击 **查看本次结果**：只分析测试开始后新增的日志，按“现在该怎么做”处理。可以点击验证、地区、模型权益或官方支持按钮，也可打开保存的报告。

没有 Python 时会明确提示并询问是否打开官方安装页；安装后重新双击。缺少 Tk 图形组件时自动使用终端按回车开始测试的等效流程。
工具不会代替你选择账号、接受条款、扫码或提交验证。

Mac 已验证诊断核心与日志采集；新图形界面尚未实机操作验证。Windows 已通过路径、代理与采集规则模拟测试，**尚未在 Windows 实机验证**。

## Mac 首次打开被拦截

下载包内附 **Mac-首次使用说明.txt**，首次打不开时先阅读。

本工具是未经过 Apple 签名/公证的开源脚本。仅在确认来源、核对内容并信任文件后，遇到“无法验证开发者”或“Apple 无法检查是否包含恶意软件”的提示，可先尝试打开，再进入 **系统设置 → 隐私与安全性 → 核对文件名 → 仍要打开**，由本人确认。

如果提示“将损坏你的电脑”、明确检测到恶意软件或文件损坏，请停止运行并核对发布文件。不要关闭系统安全保护或盲目移除隔离属性。参见 [Apple 官方说明](https://support.apple.com/zh-cn/102445)。

## 地区错误如何处理

1. 在浏览器登录与 Antigravity 相同的 Google 账号，打开 https://policies.google.com/terms 。
2. 查看条款页显示的国家/地区；若无法确认，先核对右上角登录账号。网页语言不等于账号地区。
3. 打开官方支持范围：https://www.antigravity.google/docs/faq/#what-is-google-antigravitys-geographical-availability ，同时核对实际所在地。
4. 账号关联地区与代理节点地区不是一回事；不要仅凭节点名称判断资格。
5. 若关联地区确实不符实际情况，打开 https://policies.google.com/country-association-form ，填写真实情况，由本人提交 Google 审核。
6. 提交后等待 Google 审核；申请不保证通过，也不能承诺具体生效时间。
7. 收到更正生效的通知后，正常退出 Antigravity 账号并重新登录，再开始一次登录测试。
8. 若实际所在地不受支持或仍被拒绝，向官方支持提供错误时间和本报告。脚本不能解除地区限制。

## 检查什么

- 额外账号验证：`VALIDATION_REQUIRED`、`validation_url`。
- 明确地区/年龄限制、失效凭据、OAuth 回调异常。
- DNS、TLS、网络代理、本地服务及凭据存储错误。
- 权限、企业许可证、计费和配额错误。
- 系统用户代理配置及官方域名的无凭据 HTTPS 连通性。

“待核实”是日志线索，不是确定的唯一根因。旧日志不代表当前状态；403 本身不等于地区限制。

## 边界与隐私

脚本不读取 token 文件或凭据库，不修改代理、不删缓存、不改地区、不安装软件、不购买订阅。
默认会向四个 Google 官方域名发送普通无凭据 HTTPS HEAD 请求，检查网络连通性；不会上传日志。
报告不附原始日志、token、完整验证链接或公网 IP。报告中的本地主目录会替换为 `~`。

账号地区、年龄及订阅权益须通过 Google 官方渠道处理。脚本不能绕过地区限制或开通付费模型权益，也不会自动切换账号。

工具可查找常见桌面版/CLI/IDE 日志，但不同版本日志格式和位置可能变化。没有日志时，请重现故障或手动指定日志。

## 命令行

```sh
python3 diagnose.py --offline
python3 diagnose.py --log "/path/to/your/logfile.log"
python3 diagnose.py --output "report.txt"
python3 -m unittest discover -s tests -v
```

Windows 将 `python3` 替换为 `py -3`。工具只依赖 Python 标准库，不需要管理员权限。

## 来源与问题反馈

本工具由小产品实验室制作，非 Google 官方产品，与 Google 无隶属关系。
遇到问题可在本仓库提交 Issue，请仅附脱敏的诊断报告；不要公开验证链接、凭据或原始日志。

参考：[官方 FAQ](https://www.antigravity.google/docs/faq/) · [账号验证](https://support.google.com/accounts/answer/15437069) · [模型权益](https://www.antigravity.google/docs/models/)

import unittest
from diagnose import analyze,safe_verification_urls

class DiagnosticsTests(unittest.TestCase):
    def test_specific_validation_not_generic_permission(self):
        active,_,_,_=analyze('403 PERMISSION_DENIED VALIDATION_REQUIRED Verify your account to continue.')
        self.assertEqual([x[0] for x in active],['validation'])
    def test_region_requires_explicit_evidence(self):
        active,_,_,_=analyze('PERMISSION_DENIED code 403')
        self.assertNotIn('region',[x[0] for x in active])
    def test_region_detected(self):
        self.assertIn('region',[x[0] for x in analyze('UNSUPPORTED_LOCATION')[0]])
    def test_success_supersedes_old_failure(self):
        active,history,success,urls=analyze('VALIDATION_REQUIRED\nAuth succeeded, refreshing features')
        self.assertEqual(active,[])
        self.assertEqual(history[0][0],'validation')
        self.assertTrue(success)
        self.assertEqual(urls,[])
    def test_failure_after_success_still_active(self):
        self.assertIn('validation',[x[0] for x in analyze('Auth succeeded\nVALIDATION_REQUIRED')[0]])
    def test_does_not_open_untrusted_urls(self):
        for u in ['http://accounts.google.com/signin/continue','https://accounts.google.com.evil.test/signin/continue','https://evil.test/signin/continue','https://accounts.google.com:444/signin/continue','https://user@accounts.google.com/signin/continue']:
            self.assertEqual(safe_verification_urls('"validation_url":"'+u+'"'),[])
    def test_valid_escaped_url(self):
        self.assertEqual(safe_verification_urls(r'"validation_url":"https:\/\/accounts.google.com\/signin\/continue?a=1\u0026b=2"'),['https://accounts.google.com/signin/continue?a=1&b=2'])
    def test_previous_app_session_not_current(self):
        self.assertEqual(analyze('FATAL previous session\nStarting app (v2.24.0) with dynamic port')[0],[])
    def test_quota_is_separate(self):
        self.assertEqual(analyze('RESOURCE_EXHAUSTED')[0][0][0],'quota')


class WindowsTests(unittest.TestCase):
    def test_roaming_and_cli_log_discovery(self):
        import tempfile
        from pathlib import Path
        from diagnose import log_paths
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            appdata=home/'中文 用户/AppData/Roaming'
            logfile=appdata/'Antigravity/logs/main.log'
            logfile.parent.mkdir(parents=True)
            logfile.write_text('VALIDATION_REQUIRED')
            cli=home/'.gemini/antigravity-cli/cli.log'
            cli.parent.mkdir(parents=True)
            cli.write_text('Auth succeeded')
            paths=list(log_paths(home,'win32',{'APPDATA':str(appdata)}))
            self.assertIn(logfile,paths)
            self.assertIn(cli,paths)
    def test_windows_proxy_report_hides_addresses(self):
        from diagnose import windows_proxy_summary
        result='\n'.join(windows_proxy_summary(lambda:{'ProxyEnable':1,'AutoConfigURL':'https://private.test/secret?token=123'}))
        self.assertIn('已开启',result)
        self.assertIn('已配置',result)
        self.assertNotIn('private.test',result)
        self.assertNotIn('token',result)
    def test_windows_registry_failure(self):
        from diagnose import windows_proxy_summary
        def denied():raise PermissionError('private registry')
        self.assertIn('无法读取',windows_proxy_summary(denied)[0])

if __name__=='__main__':unittest.main()

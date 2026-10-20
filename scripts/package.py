"""Build shareable packages from an explicit allowlist; excludes local reports."""
from pathlib import Path
import hashlib
import zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'site/downloads'
OUT.mkdir(parents=True,exist_ok=True)
checks=[]
for system,launcher in [('macos','Start-Diagnostics.command'),('windows','Start-Diagnostics.bat')]:
    filename='antigravity-diagnostics-'+system+'.zip'
    with zipfile.ZipFile(OUT/filename,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ['diagnose.py',launcher,'README.md']:
            archive.write(ROOT/name,'antigravity-diagnostics/'+name)
    with zipfile.ZipFile(OUT/filename) as archive:
        assert archive.testzip() is None
    checks.append(hashlib.sha256((OUT/filename).read_bytes()).hexdigest()+'  '+filename)
(OUT/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='utf-8')
print('\n'.join(checks))

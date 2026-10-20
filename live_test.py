"""Capture only log content written after a user starts a login test."""
import hashlib
import json
from pathlib import Path

LIMIT=2_000_000

def identity(path):
    with path.open('rb') as f:
        head=f.read(1024)
    stat=path.stat()
    return {'size':stat.st_size,'head_len':len(head),'head':hashlib.sha256(head).hexdigest()}

def capture(paths):
    out={}
    for path in paths:
        try:out[str(path.resolve())]=identity(path)
        except OSError:pass
    return out

def fresh_tail(path,snapshot):
    previous=snapshot.get(str(path.resolve()))
    with path.open('rb') as f:
        f.seek(0,2);size=f.tell()
        offset=0
        if previous and size>=previous['size']:
            f.seek(0)
            if hashlib.sha256(f.read(previous['head_len'])).hexdigest()==previous['head']:
                offset=previous['size']
        f.seek(max(offset,size-LIMIT))
        data=f.read()
    return data.decode('utf-8',errors='replace')

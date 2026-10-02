"""Audit Git history and publishable working files without printing any secret values."""
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from check_staged import ROOT, BLOCKED_DIRS, BLOCKED_SUFFIXES, TOKEN_PATTERN


def main():
    known=[]
    for path in (ROOT/'secrets').glob('*'):
        if not path.is_file() or path.suffix == '.pub':
            continue
        text=path.read_text(encoding='utf-8-sig').strip()
        if path.suffix=='.json':
            values=json.loads(text)
            known.extend(str(v).encode() for k,v in values.items() if k in {'token','password','key'} and len(str(v))>=8)
        elif len(text)>=8:
            known.append(text.encode())
    for line in (ROOT/'.env').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key,value=line.split('=',1)
            if re.search('PASSWORD|TOKEN|SECRET',key,re.I) and len(value)>=8:known.append(value.encode())
    def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
    errors=[]
    def inspect(name,data):
        path=PurePosixPath(name)
        if (any(p.lower() in BLOCKED_DIRS for p in path.parts) or path.suffix.lower() in BLOCKED_SUFFIXES
            or (path.name.startswith('.env') and path.name!='.env.example')):
            errors.append(name+': forbidden path')
        if len(data)>5*1024*1024:errors.append(name+': oversized file')
        if TOKEN_PATTERN.search(data) or any(s in data for s in known):errors.append(name+': possible secret (withheld)')
    objects=git('rev-list','--objects','--all').decode().splitlines()
    count=0
    for line in objects:
        fields=line.split(' ',1)
        if len(fields)!=2:continue
        oid,name=fields
        if git('cat-file','-t',oid).strip()!=b'blob':continue
        inspect(name,git('cat-file','blob',oid));count+=1
    names=set(filter(None,git('ls-files','-co','--exclude-standard','-z').decode().split('\0')))
    for name in names:
        if (ROOT/name).is_file():inspect(name,(ROOT/name).read_bytes())
    result={'history_blobs':count,'working_files':len(names),'errors':errors,'passed':not errors}
    folder=ROOT/'reports/final';folder.mkdir(parents=True,exist_ok=True)
    (folder/'secret-audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()

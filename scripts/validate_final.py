"""Prepublication tests of a working-tree snapshot, explicitly distinct from a Git checkout."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tarfile

from jenkins_local import ROOT, connect
from jenkins_remote import configure_job, run


def main():
    p=argparse.ArgumentParser();p.add_argument('--fault',choices=['none','pytest','candidate-smoke','post-deploy'],default='none');args=p.parse_args()
    names=subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    paths=sorted({n for n in names if n and (ROOT/n).is_file()})
    for name in paths:
        if any(x in Path(name).parts for x in ('secrets','reports','.venv','Insumos','.git')) or Path(name).name=='.env':
            raise RuntimeError('Forbidden snapshot input')
    digest=hashlib.sha256()
    for name in paths:digest.update(name.encode()+b'\0'+(ROOT/name).read_bytes())
    revision='snapshot-sha256-'+digest.hexdigest()
    folder=ROOT/'reports/final/snapshots';folder.mkdir(parents=True,exist_ok=True)
    archive=folder/(revision+'.tar')
    with tarfile.open(archive,'w') as tar:
        for name in paths:tar.add(ROOT/name,arcname=name,recursive=False)
    remote='/var/jenkins_home/local-sources/'+archive.name
    subprocess.run(['docker','compose','cp',str(archive),'jenkins:'+remote],cwd=ROOT,check=True)
    script=(ROOT/'Jenkinsfile').read_text()
    script=script.replace('    triggers { githubPush() }\n','')
    script=script.replace('    environment {','    environment {\n        CI_SOURCE_SNAPSHOT = "'+revision+'"',1)
    script=script.replace('                    checkout scm',"                    sh 'tar -xf "+remote+"'")
    client=connect();configure_job(client,'parcialbigdata-validation-local','working-tree snapshot',script=script)
    run(client,'parcialbigdata-validation-local',args.fault)
    print('Source:',revision,'(not a Git commit)')


if __name__=='__main__':main()

"""Run and measure Spark against the existing Docker services, without Git changes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--label',default='spark')
    args=parser.parse_args()
    if not args.label.replace('-','').replace('_','').isalnum():
        parser.error('Label must be alphanumeric')
    directory=ROOT/'reports/phase4'
    directory.mkdir(parents=True,exist_ok=True)
    stop=threading.Event()
    def monitor():
        with (directory/(args.label+'-resources.jsonl')).open('w',encoding='utf-8') as stream:
            while not stop.is_set():
                ids=subprocess.check_output(['docker','compose','ps','-q'],cwd=ROOT,text=True).split()
                raw=subprocess.check_output(['docker','stats','--no-stream','--format','{{json .}}',*ids],text=True)
                stream.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'containers':[json.loads(line) for line in raw.splitlines()]})+'\n')
                stream.flush()
                stop.wait(3)
    thread=threading.Thread(target=monitor,daemon=True)
    thread.start()
    command=['docker','compose','exec','-T','spark-master','/opt/spark/bin/spark-submit',
             '/opt/processing/run_tests.py' if args.test else '/opt/processing/job.py']
    if args.force and not args.test:command.append('--force')
    start=time.monotonic()
    try:
        with (directory/(args.label+'.log')).open('w',encoding='utf-8') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    finally:
        stop.set();thread.join(timeout=15)
    metadata={'exit_code':result.returncode,'wall_seconds':time.monotonic()-start,'test':args.test,'force':args.force}
    (directory/(args.label+'-execution.json')).write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata))
    if result.returncode==0:
        source='/scratch/spark-tests.xml' if args.test else '/data/analytics-report.json'
        subprocess.run(['docker','compose','cp','spark-master:'+source,str(directory/(args.label+('.xml' if args.test else '.json')))],cwd=ROOT,check=True)
    raise SystemExit(result.returncode)


if __name__=='__main__':main()

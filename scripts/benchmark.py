"""Sequential benchmark on isolated workers; restores the existing compute services."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmark.metrics import mib, parse_stats
COMPUTE = ['spark-master','spark-worker','dask-scheduler','dask-worker-1','dask-worker-2']
BASE = ['docker','compose']
BENCH = BASE + ['--project-name','pbd-benchmark','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'ci/compose.benchmark.yml')]


def command(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def output(args):
    return subprocess.check_output(args,cwd=ROOT,text=True).strip()


def counters(container):
    code = "import json,pathlib; print(json.dumps({n:dict(line.split() for line in pathlib.Path('/sys/fs/cgroup/'+n).read_text().splitlines()) for n in ['cpu.stat','memory.events']}))"
    return json.loads(output(['docker','exec',container,'python3','-c',code]))


def wait_ready(engine,workers,service):
    if engine == 'spark':
        code = "import json,urllib.request; d=json.load(urllib.request.urlopen('http://bench-spark-master:8080/json/')); assert sum(w['state']=='ALIVE' for w in d['workers'])=="+str(workers)
    else:
        code = "from distributed import Client; c=Client('tcp://bench-dask-scheduler:8786'); c.wait_for_workers("+str(workers)+",timeout=5); assert len(c.scheduler_info()['workers'])=="+str(workers)+"; c.close()"
    for attempt in range(30):
        result=subprocess.run(BENCH+['exec','-T',service,'python3','-c',code],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode==0:return
        time.sleep(2)
    raise RuntimeError('Benchmark workers did not become ready')


def run_once(engine, workers, iteration, directory, service):
    label=f'{engine}-{workers}-'+('warmup' if iteration==0 else f'run-{iteration}')
    engine_ids=output(BENCH+['ps','-q']).split()
    production_ids=output(BASE+['ps','-q']).split()
    names={c:output(['docker','inspect','--format','{{.Name}}',c]).lstrip('/') for c in engine_ids}
    samples=[]; ready=threading.Event()
    stats=subprocess.Popen(['docker','stats','--format','{{json .}}',*engine_ids,*production_ids],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    def monitor():
        for line in stats.stdout:
            try:
                # Docker emits ANSI cursor controls even when stdout is a pipe.
                sample=parse_stats(line); sample['sample_unix']=time.time();samples.append(sample);ready.set()
            except ValueError:pass
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    ready.wait(10)
    result_path='/scratch/'+label+'.json'
    args=['python','-m','benchmark.run',engine]
    if engine=='spark':
        command(BENCH+['exec','-T',service,'python3','-c',"from pathlib import Path; Path('/scratch/events').mkdir(exist_ok=True)"])
        args=['/opt/spark/bin/spark-submit','--master','spark://bench-spark-master:7077',
              '--conf','spark.driver.host=bench-spark-master','--conf',f'spark.cores.max={workers}',
              '--conf','spark.sql.adaptive.enabled=false','--conf','spark.eventLog.enabled=true',
              '--conf','spark.sql.files.minPartitionNum=1',
              '--conf','spark.eventLog.dir=file:/scratch/events','--conf','spark.task.maxFailures=1',
              '/opt/benchmark/run.py',engine]
    cpu_start=time.perf_counter()
    before={c:counters(c) for c in engine_ids}
    started=time.time(); start=time.perf_counter()
    try:
        with (directory/(label+'.log')).open('w',encoding='utf-8') as stream:
            process=subprocess.run(BENCH+['exec','-T',service,*args,'--workers',str(workers),'--output',result_path],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        wall=time.perf_counter()-start; ended=time.time()
    finally:
        stats.terminate();thread.join(timeout=10);stats.wait(timeout=10)
    after={c:counters(c) for c in engine_ids}
    cpu_window=time.perf_counter()-cpu_start
    (directory/(label+'-samples.json')).write_text(json.dumps(samples,indent=2))
    record={'engine':engine,'workers':workers,'iteration':iteration,'warmup':iteration==0,
            'utc':datetime.fromtimestamp(started,timezone.utc).isoformat(),'total_seconds':wall,
            'exit_code':process.returncode,'counters_before':before,'counters_after':after}
    selected=[s for s in samples if started<=s['sample_unix']<=ended and s['Name'] in names.values()]
    # Each frame contains one sample per container. Bucket by Docker's ~1-second cycle.
    frames={}
    for s in selected:frames.setdefault(round(s['sample_unix']),{})[s['Name']]=s
    complete=[f for f in frames.values() if len(f)==len(engine_ids)]
    if not complete:raise RuntimeError('No complete engine memory samples; do not report invented peaks')
    record['sample_frames']=len(complete)
    record['engine_peak_mib']=max(sum(mib(s['MemUsage']) for s in f.values()) for f in complete)
    record['container_peaks_mib']={n:max(mib(s['MemUsage']) for s in selected if s['Name']==n) for n in names.values()}
    record['cpu_seconds']=sum((int(after[c]['cpu.stat']['usage_usec'])-int(before[c]['cpu.stat']['usage_usec']))/1e6 for c in engine_ids)
    record['cpu_window_seconds']=cpu_window
    record['cpu_average_cores']=record['cpu_seconds']/cpu_window
    record['oom_kill_delta']=sum(int(after[c]['memory.events']['oom_kill'])-int(before[c]['memory.events']['oom_kill']) for c in engine_ids)
    if process.returncode==0:
        command(BENCH+['cp',service+':'+result_path,str(directory/(label+'.json'))],stdout=subprocess.DEVNULL)
        record.update(json.loads((directory/(label+'.json')).read_text()))
        if engine=='spark':
            code="import pathlib,json; p=max(pathlib.Path('/scratch/events').glob('*'),key=lambda p:p.stat().st_mtime); e=[json.loads(l) for l in p.read_text().splitlines()]; print(json.dumps({'failed_task_events':sum(x['Event']=='SparkListenerTaskEnd' and x['Task End Reason']['Reason']!='Success' for x in e),'task_retries':sum(x['Event']=='SparkListenerTaskStart' and x['Task Info']['Attempt']>0 for x in e),'workers_used':len({x['Task Info']['Executor ID'] for x in e if x['Event']=='SparkListenerTaskEnd'})}))"
            record.update(json.loads(output(BENCH+['exec','-T',service,'python3','-c',code])))
    (directory/(label+'-metrics.json')).write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v for k,v in record.items() if not k.startswith('counters')}),flush=True)
    if process.returncode or record['oom_kill_delta']:raise RuntimeError(f'{label} failed; see retained logs')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',default=datetime.now(timezone.utc).strftime('benchmark-%Y%m%dT%H%M%SZ'))
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if not args.label.replace('-','').replace('_','').isalnum() or not 1<=args.repeats<=10:parser.error('Invalid label or repeats')
    directory=ROOT/'reports/phase5'/args.label
    directory.mkdir(parents=True,exist_ok=False)
    source_files=[ROOT/'scripts/benchmark.py', ROOT/'ci/compose.benchmark.yml',*sorted((ROOT/'benchmark').glob('*.py')),ROOT/'processing/aggregates.py']
    info=json.loads(output(['docker','info','--format','{{json .}}']))
    metadata={'platform':platform.platform(),'logical_cpus_host':os.cpu_count(),
              'docker_memory_bytes':info['MemTotal'],'docker_cpus':info['NCPU'],'docker_server':info['ServerVersion'],
              'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
              'source_commit_before_phase_close':output(['git','rev-parse','HEAD']),
              'images':{name:output(['docker','image','inspect','--format','{{.Id}}',name]) for name in ['parcialbigdata-spark:phase1','parcialbigdata-dask:phase1']}}
    (directory/'environment.json').write_text(json.dumps(metadata,indent=2))
    command(BENCH+['config','--quiet'])
    with (directory/'preparation.log').open('w') as stream:
        command(BENCH+['run','--rm','snapshot'],stdout=stream,stderr=subprocess.STDOUT)
    if args.prepare_only:return
    original=output(BASE+['ps','--services','--status','running']).split()
    restore=[s for s in COMPUTE if s in original]
    records=[]
    # Reverse the engine order between worker counts to limit a single ordering bias.
    order=[('dask',1),('spark',1),('spark',2),('dask',2)]
    try:
        command(BASE+['stop',*COMPUTE])
        for engine,workers in order:
            service='bench-'+engine+('-master' if engine=='spark' else '-scheduler')
            services=[service]+[f'bench-{engine}-worker-{i}' for i in range(1,workers+1)]
            command(BENCH+['up','-d','--no-build',*services])
            wait_ready(engine,workers,service)
            command(BENCH+['cp',service+':/data/benchmark-v1/manifest.json',str(directory/'manifest.json')],stdout=subprocess.DEVNULL)
            for i in range(args.repeats+1):
                records.append(run_once(engine,workers,i,directory,service))
                (directory/'results.json').write_text(json.dumps(records,indent=2))
            if engine=='spark':command(BENCH+['cp',service+':/scratch/events',str(directory/f'spark-{workers}-events')],stdout=subprocess.DEVNULL)
            for s in services:
                with (directory/(s+'.log')).open('w') as stream:command(BENCH+['logs','--no-color',s],stdout=stream,stderr=subprocess.STDOUT)
            command(BENCH+['down'])
        assert len({r['grid_sha256'] for r in records})==1
        print('PASS: all configurations and repetitions match every reference cell/count')
    finally:
        command(BENCH+['down'])
        if restore:command(BASE+['start','--wait',*restore])


if __name__=='__main__':main()

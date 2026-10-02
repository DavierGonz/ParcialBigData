"""Isolated same-host reproduction; temporarily stops base services, never deletes volumes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ['api', 'jenkins', 'spark-worker', 'spark-master', 'dask-worker-1',
            'dask-worker-2', 'dask-scheduler', 'mongodb']


def main():
    folder = ROOT / 'reports/reproduction'
    target = folder / 'checkout'
    folder.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise RuntimeError('Reproduction checkout already exists; preserve evidence and use a fresh directory.')
    log = (folder / 'execution.log').open('w', encoding='utf-8')
    steps = []
    def run(args, cwd=target, env=None):
        started = time.perf_counter()
        result = subprocess.run(args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        log.flush()
        steps.append({'command': args, 'seconds': time.perf_counter()-started, 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError('Reproduction command failed; inspect reports/reproduction/execution.log')
    run(['git', 'clone', '--no-local', '--branch', 'develop/final-delivery', str(ROOT), str(target)], ROOT)
    # Prepublication copy: only Git-eligible source files, no credentials or runtime state.
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    manifest = {}
    for name in sorted(set(filter(None, names))):
        source = ROOT / name
        if not source.is_file():
            continue
        if any(p in Path(name).parts for p in ('secrets', 'reports', '.venv', '.git', 'Insumos')) or Path(name).name == '.env':
            raise RuntimeError('Forbidden reproduction input')
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        manifest[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    (folder / 'source-manifest.json').write_text(json.dumps(manifest, indent=2))
    run(['py', '-3.10', '-m', 'venv', '.venv'])
    python = str(target / '.venv/Scripts/python.exe')
    run([python, '-m', 'pip', 'install', '-r', 'requirements/local.txt'])
    run([python, '-m', 'pip', 'check'])
    run([python, '-m', 'pytest', '-q', '--junitxml=reports/reproduction-tests.xml'])
    run([python, 'scripts/init_env.py'])
    text = (target / '.env').read_text()
    for old, new in [('COMPOSE_PROJECT_NAME=parcialbigdata', 'COMPOSE_PROJECT_NAME=pbd-repro'),
                     ('API_PORT=5000','API_PORT=15000'), ('JENKINS_PORT=8080','JENKINS_PORT=18080'),
                     ('SPARK_UI_PORT=8081','SPARK_UI_PORT=18081'), ('DASK_UI_PORT=8787','DASK_UI_PORT=18787')]:
        text = text.replace(old, new)
    (target / '.env').write_text(text+'\nAPI_IMAGE=pbd-repro-api:final\n')
    try:
        run(['docker','compose','stop',*SERVICES], ROOT)
        run(['docker','compose','config','--quiet'])
        run(['docker','compose','build','api-tests'])
        run(['docker','compose','run','--rm','--no-deps','api-tests'])
        run(['docker','compose','up','-d','--build','--wait','--wait-timeout','300'])
        run([python,'scripts/verify_infra.py'])
        ingest = ['docker','compose','-f','docker-compose.yml','-f','ci/compose.ingestion.yml']
        run(ingest+['build','ingestion-tests'])
        run(ingest+['run','--rm','--no-deps','ingestion-tests'])
        # Create the shared lock file explicitly; no dataset is copied or downloaded.
        run(['docker','compose','exec','-T','dask-worker-1','python','-c',"open('/data/.ingestion.lock','a').close()"])
        run(['docker','compose','exec','-T','spark-master','/opt/spark/bin/spark-submit','/opt/processing/run_tests.py'])
        run(['docker','compose','-f','docker-compose.yml','-f','ci/compose.integration.yml','run','--rm','--no-deps','api-integration',
             'python','-m','pytest','tests_api_integration','-q','-k','not real_sample_and_analytics_coherence'])
        run(['docker','stats','--no-stream','--format','{{json .}}'])
    finally:
        run(['docker','compose','stop'])
        run(['docker','compose','start','--wait',*SERVICES], ROOT)
        (folder / 'steps.json').write_text(json.dumps(steps, indent=2))
        log.close()
    print('PASS: new checkout, venv, credentials and volumes on SAME Windows/Docker host; evidence:', folder)


if __name__ == '__main__':
    main()

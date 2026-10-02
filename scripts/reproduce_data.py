"""Complete a same-host reproduction with a fresh cache and explicitly provisioned Kaggle token."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / 'reports/reproduction'
    target = folder / 'checkout'
    if not (target / '.env').exists():
        raise RuntimeError('Run reproduce_clean.py first')
    # Only the external Kaggle credential is provisioned; no database/cache/hidden config is copied.
    secret = ROOT / 'secrets/kaggle-token.txt'
    if not secret.exists():
        raise RuntimeError('Provision secrets/kaggle-token.txt as documented in README')
    environment = dict(os.environ, KAGGLE_CREDENTIAL=secret.read_text().strip())
    steps = []
    with (folder / 'data-execution.log').open('w', encoding='utf-8') as log:
        def run(args, cwd=target, env=None):
            start = time.perf_counter()
            result = subprocess.run(args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
            log.flush()
            steps.append({'command': args, 'seconds': time.perf_counter()-start, 'exit_code': result.returncode})
            if result.returncode:
                raise RuntimeError('Reproduction failed; inspect data-execution.log (secret values not logged)')
        try:
            run(['docker','compose','stop'], ROOT)
            run(['docker','compose','start','--wait'])
            ingest = ['docker','compose','-f','docker-compose.yml','-f','ci/compose.ingestion.yml']
            run(ingest+['build','ingestion'])
            run(ingest+['run','--rm','--no-deps','ingestion'], env=environment)
            run(['docker','compose','cp','spark-master:/data/last-ingestion-report.json',str(folder/'ingestion.json')])
            run([str(target/'.venv/Scripts/python.exe'),'scripts/run_spark.py','--label','clean-reproduction'])
            run(['docker','compose','-f','docker-compose.yml','-f','ci/compose.integration.yml','run','--rm','--no-deps','api-integration'])
            run([str(target/'.venv/Scripts/python.exe'),'scripts/smoke_geo.py','http://127.0.0.1:15000'])
            run(['docker','stats','--no-stream','--format','{{json .}}'])
        finally:
            try:
                run(['docker','compose','stop'])
            finally:
                run(['docker','compose','start','--wait'], ROOT)
                (folder/'data-steps.json').write_text(json.dumps(steps, indent=2))
    print('PASS: independent complete dataset download, ETL, Spark and HTTP in fresh same-host volumes.')


if __name__ == '__main__':
    main()

"""Validate and publish small, non-secret measurement artifacts and Markdown tables."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import statistics as stats
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmark.metrics import mib


def summarize(records):
    assert len({r['grid_sha256'] for r in records}) == 1
    assert all(r['exit_code']==0 and r['sum_counts']==1103657 and r['records_processed']==1103657
               and r['cells']==23599 and r['workers_used']==r['workers'] for r in records)
    rows=[]
    for engine in ('dask','spark'):
        for workers in (1,2):
            group=[r for r in records if r['engine']==engine and r['workers']==workers and not r['warmup']]
            warm=[r for r in records if r['engine']==engine and r['workers']==workers and r['warmup']]
            assert len(group)>=2 and len(warm)==1, 'Formal summary needs >=2 measured runs plus one warmup per configuration'
            rows.append({'engine':engine,'workers':workers,'n':len(group),
                         'total_median_s':stats.median(r['total_seconds'] for r in group),
                         'total_min_s':min(r['total_seconds'] for r in group),
                         'total_max_s':max(r['total_seconds'] for r in group),
                         'operation_median_s':stats.median(r['operation_seconds'] for r in group),
                         'engine_peak_mib':max(r['engine_peak_mib'] for r in group),
                         'cpu_seconds_median':stats.median(r['cpu_seconds'] for r in group),
                         'cpu_cores_median':stats.median(r['cpu_average_cores'] for r in group),
                         'errors':sum(r['errors']+r['failed_task_events'] for r in group),
                         'retries':sum(r['task_retries'] for r in group),
                         'oom_kills':sum(r['oom_kill_delta'] for r in group)})
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    records=json.loads((args.source/'results.json').read_text())
    rows=summarize(records)
    args.output.mkdir(parents=True,exist_ok=True)
    for name in ('results.json','manifest.json','environment.json'):
        if (args.source/name).resolve()!=(args.output/name).resolve():shutil.copyfile(args.source/name,args.output/name)
    samples=args.output/'samples';samples.mkdir(exist_ok=True)
    sample_source=args.source if list(args.source.glob('*-samples.json')) else args.source/'samples'
    peak_all=0; individual={}
    for path in sample_source.glob('*-samples.json'):
        if path.resolve()!=(samples/path.name).resolve():shutil.copyfile(path,samples/path.name)
    for record in records:
        label=f"{record['engine']}-{record['workers']}-"+('warmup' if record['warmup'] else f"run-{record['iteration']}")
        raw=json.loads((samples/(label+'-samples.json')).read_text())
        start=datetime.fromisoformat(record['utc']).timestamp(); end=start+record['total_seconds']; frames={}
        for sample in raw:
            if start<=sample['sample_unix']<=end:
                frames.setdefault(round(sample['sample_unix']),{})[sample['Name']]=sample
                individual[sample['Name']]=max(individual.get(sample['Name'],0),mib(sample['MemUsage']))
        for frame in frames.values():
            if len(frame)==record['workers']+4:peak_all=max(peak_all,sum(mib(s['MemUsage']) for s in frame.values()))
    (args.output/'resources.json').write_text(json.dumps({'all_services_peak_mib':peak_all,'individual_peak_mib':individual},indent=2))
    (args.output/'summary.json').write_text(json.dumps(rows,indent=2))
    lines=['# Tablas generadas desde resultados reales','',
           '| Motor | Workers | n | Total mediana s | Min–max s | Operación mediana s | Pico motor MiB | CPU s mediana | CPU cores mediana | Errores / reintentos / OOM |',
           '|---|---:|---:|---:|---|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['engine']} | {r['workers']} | {r['n']} | {r['total_median_s']:.3f} | {r['total_min_s']:.3f}–{r['total_max_s']:.3f} | {r['operation_median_s']:.3f} | {r['engine_peak_mib']:.1f} | {r['cpu_seconds_median']:.3f} | {r['cpu_cores_median']:.3f} | {r['errors']} / {r['retries']} / {r['oom_kills']} |")
    lines+=['','## Ejecuciones individuales (calentamientos separados)','',
            '| Motor | Workers | Tipo / iteración | Total s | Operación s | Pico MiB | CPU s | Frames memoria | Registros / celdas / suma |',
            '|---|---:|---|---:|---:|---:|---:|---:|---|']
    for r in records:
        kind='calentamiento' if r['warmup'] else str(r['iteration'])
        lines.append(f"| {r['engine']} | {r['workers']} | {kind} | {r['total_seconds']:.3f} | {r['operation_seconds']:.3f} | {r['engine_peak_mib']:.1f} | {r['cpu_seconds']:.3f} | {r['sample_frames']} | {r['records_processed']} / {r['cells']} / {r['sum_counts']} |")
    (args.output/'tablas.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()

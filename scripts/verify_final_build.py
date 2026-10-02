"""Collect Jenkins evidence and assert promotion/rollback against the captured API state."""
import argparse
import json
import xml.etree.ElementTree as ET
from jenkins_remote import ROOT, connect, status, api_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('number', type=int)
    parser.add_argument('--job', default='parcialbigdata-validation')
    args = parser.parse_args()
    client = connect()
    status(client, args.job, args.number)
    folder = ROOT / 'reports/final' / args.job / str(args.number)
    if not (folder / 'build.json').exists():
        raise SystemExit('Build is still running; retry after completion.')
    build = json.loads((folder / 'build.json').read_text())
    before_path = folder.parent / f'{args.number}-before.json'
    captured = json.loads(before_path.read_text()) if before_path.exists() else {'fault': 'none'}
    fault = captured['fault']
    suites = {}
    for path in folder.glob('*.xml'):
        root = ET.parse(path).getroot()
        nodes = list(root.iter('testsuite'))
        suites[path.name] = {k: sum(int(n.get(k, 0)) for n in nodes)
                             for k in ('tests', 'failures', 'errors', 'skipped')}
    after = api_state()
    if fault == 'pytest':
        assert build['result'] == 'FAILURE'
        assert suites['pytest.xml']['failures'] == 1
        assert captured['before'] == after
        assert not (folder / 'deployment.txt').exists()
    elif fault == 'post-deploy':
        assert build['result'] == 'FAILURE'
        assert (folder / 'rollback.txt').read_text().strip() == 'rollback completed'
        assert captured['before']['image'] == after['image']
        assert not (folder / 'deployment.txt').exists()
        assert all(v['failures'] == v['errors'] == 0 for v in suites.values())
    else:
        assert fault == 'none' and build['result'] == 'SUCCESS'
        assert all(v['failures'] == v['errors'] == 0 for v in suites.values())
        revision = (folder / 'source-commit.txt').read_text().strip()
        deployment = (folder / 'deployment.txt').read_text().strip()
        assert deployment == after['image'] + ' revision=' + revision
    result = {'job': args.job, 'number': args.number, 'fault': fault,
              'verified': True, 'duration_seconds': build['duration'] / 1000,
              'suites': suites, 'after': after}
    (folder / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

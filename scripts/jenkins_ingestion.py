"""Prepare and run only the local ingestion job; never push or deploy Flask."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET

import jenkins_local as local

JOB = 'parcialbigdata-ingestion-local'
CREDENTIAL = 'parcialbigdata-kaggle'
REPORTS = local.ROOT / 'reports/ingestion-jenkins'


def credential(client):
    base = 'credentials/store/system/domain/_/'
    credentials = client.get(base + 'api/json?tree=credentials[id]')['credentials']
    if any(item['id'] == CREDENTIAL for item in credentials):
        print('Kaggle credential already registered in Jenkins; value not read.')
        return
    paths = [local.ROOT / 'secrets/kaggle-token.txt', local.ROOT / 'secrets/kaggle.json']
    path = next((path for path in paths if path.is_file()), None)
    if path is None:
        raise RuntimeError('Save Kaggle token in secrets/kaggle-token.txt or secrets/kaggle.json; do not paste it in chat.')
    value = path.read_text(encoding='utf-8-sig').strip()
    if not value:
        raise ValueError('Empty Kaggle credential file')
    if path.suffix == '.json':
        parsed = json.loads(value)
        if not parsed.get('username') or not parsed.get('key'):
            raise ValueError('Kaggle JSON requires username and key')
    payload = {'credentials': {'scope': 'GLOBAL', 'id': CREDENTIAL,
               'description': local.MARKER + ': Kaggle ingestion', 'secret': value,
               '$class': 'org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl'}}
    client.request(base + 'createCredentials', {'json': json.dumps(payload)}).close()
    print('Kaggle credential registered securely; value not displayed.')


def run(client, validate_only, force_etl):
    if not validate_only:
        credential(client)
    local.JOB = JOB
    local.PIPELINE_FILE = 'ci/Jenkinsfile.ingestion'
    revision = local.prepare(client)
    # Install all parameters before the first build, without running a bootstrap build.
    with client.request(f'job/{JOB}/config.xml') as response:
        root = ET.fromstring(response.read())
    definitions = root.find('./properties/hudson.model.ParametersDefinitionProperty/parameterDefinitions')
    definitions.clear()
    for name, value, kind in [('LOCAL_COMMIT', revision, 'String'),
                              ('VALIDATE_ONLY', str(validate_only).lower(), 'Boolean'),
                              ('FORCE_ETL', str(force_etl).lower(), 'Boolean')]:
        element = ET.SubElement(definitions, f'hudson.model.{kind}ParameterDefinition')
        ET.SubElement(element, 'name').text = name
        ET.SubElement(element, 'defaultValue').text = value
    client.request(f'job/{JOB}/config.xml', ET.tostring(root), 'application/xml').close()
    with client.request(f'job/{JOB}/buildWithParameters',
                        {'LOCAL_COMMIT': revision, 'VALIDATE_ONLY': str(validate_only).lower(),
                         'FORCE_ETL': str(force_etl).lower()}) as response:
        queue = urllib.parse.urlsplit(response.headers['Location']).path
    for _ in range(30):
        info = client.get(queue + 'api/json')
        if 'executable' in info:
            number = info['executable']['number']
            REPORTS.mkdir(parents=True, exist_ok=True)
            state = {'number': number, 'commit': revision, 'validate_only': validate_only,
                     'force_etl': force_etl, 'before': local.api_state()}
            (REPORTS / f'build-{number}.json').write_text(json.dumps(state, indent=2))
            print(f'Build #{number}: {client.url}/job/{JOB}/{number}/')
            return
        if info.get('cancelled'):
            raise RuntimeError('Build cancelled')
        time.sleep(1)
    raise RuntimeError('Build remains queued; inspect Jenkins')


def status(client, number):
    info = client.get(f'job/{JOB}/{number}/api/json?tree=result,building,duration,artifacts[fileName,relativePath]')
    print(json.dumps(info, indent=2))
    if info['building']:
        return
    directory = REPORTS / f'build-{number}'
    directory.mkdir(parents=True, exist_ok=True)
    # Jenkins masks credentials; never print or store the console via this tool.
    for item in info['artifacts']:
        if item['fileName'] != Path(item['relativePath']).name:
            raise RuntimeError('Unexpected artifact name')
        with client.request(f'job/{JOB}/{number}/artifact/' + urllib.parse.quote(item['relativePath'])) as response:
            (directory / item['fileName']).write_bytes(response.read())
    if info['result'] != 'SUCCESS':
        raise RuntimeError('Jenkins failed; inspect its masked console')
    record = json.loads((REPORTS / f'build-{number}.json').read_text())
    assert (directory / 'source-commit.txt').read_text().strip() == record['commit']
    for suite in ('unit', 'integration'):
        cases = ET.parse(directory / f'ingestion-{suite}.xml').findall('.//testcase')
        assert cases and all(case.find('failure') is None and case.find('error') is None for case in cases)
    assert (directory / 'api-before.txt').read_text() == (directory / 'api-after.txt').read_text()
    assert local.api_state() == record['before'], 'Flask deployment changed'
    if not record['validate_only']:
        report = json.loads((directory / 'ingestion.json').read_text())
        assert report['verification']['stored'] >= 1_000_000
    record.update(verified=True, result=info['result'], duration_ms=info['duration'])
    (REPORTS / f'build-{number}.json').write_text(json.dumps(record, indent=2))
    print('PASS: tests, source revision, artifacts and unchanged Flask deployment verified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('credential')
    runner = commands.add_parser('run')
    runner.add_argument('--validate-only', action='store_true')
    runner.add_argument('--force-etl', action='store_true')
    commands.add_parser('status').add_argument('number', type=int)
    args = parser.parse_args()
    client = local.connect()
    if args.action == 'credential':
        credential(client)
    elif args.action == 'run':
        run(client, args.validate_only, args.force_etl)
    else:
        status(client, args.number)


if __name__ == '__main__':
    main()

"""Operate the real local Jenkins using committed Git bundles, never GitHub pushes."""
import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SECRET = ROOT / 'secrets/jenkins-local-api.json'
REPORTS = ROOT / 'reports/jenkins'
JOB = 'parcialbigdata-local'
MARKER = 'Managed by ParcialBigData local CI'
CREDENTIAL = 'parcialbigdata-compose-env'
PIPELINE_FILE = 'ci/Jenkinsfile.local'


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.PIPE).strip()


class Jenkins:
    def __init__(self, username, token, url='http://127.0.0.1:8080'):
        self.url = url.rstrip('/')
        self.auth = 'Basic ' + base64.b64encode(f'{username}:{token}'.encode()).decode()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.crumb = None

    def request(self, path, data=None, content_type=None):
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data).encode()
            content_type = 'application/x-www-form-urlencoded'
        headers = {'Authorization': self.auth}
        if data is not None:
            if self.crumb is None:
                self.crumb = self.get('crumbIssuer/api/json')
            headers[self.crumb['crumbRequestField']] = self.crumb['crumb']
        if content_type:
            headers['Content-Type'] = content_type
        return self.opener.open(urllib.request.Request(self.url + '/' + path.lstrip('/'), data=data, headers=headers), timeout=30)

    def get(self, path):
        with self.request(path) as response:
            return json.load(response)


def connect():
    if not SECRET.exists():
        password = command('docker', 'compose', 'exec', '-T', 'jenkins', 'cat',
                           '/var/jenkins_home/secrets/initialAdminPassword')
        client = Jenkins('admin', password)
        with client.request('me/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken',
                            {'newTokenName': 'parcialbigdata-local-ci'}) as response:
            token = json.load(response)['data']['tokenValue']
        SECRET.parent.mkdir(exist_ok=True)
        with SECRET.open('x', encoding='utf-8') as stream:
            json.dump({'username': 'admin', 'token': token, 'url': client.url}, stream)
        os.chmod(SECRET, 0o600)
        print('Created a local Jenkins API token in ignored secrets/ (value not displayed).')
    settings = json.loads(SECRET.read_text())
    client = Jenkins(**settings)
    client.get('api/json?tree=nodeName')
    return client


def configure_credential(client):
    env_text = (ROOT / '.env').read_text(encoding='utf-8')
    if 'COMPOSE_PROJECT_NAME=parcialbigdata' not in env_text.splitlines():
        raise RuntimeError('This local pipeline targets COMPOSE_PROJECT_NAME=parcialbigdata only.')
    base = 'credentials/store/system/domain/_/'
    try:
        with client.request(base + f'credential/{CREDENTIAL}/config.xml') as response:
            existing = ET.fromstring(response.read())
        if not existing.findtext('description', '').startswith(MARKER):
            raise RuntimeError('Refusing to replace a credential not managed by this project.')
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        payload = {'credentials': {'scope': 'GLOBAL', 'id': CREDENTIAL,
                   'description': MARKER + ': Compose environment', 'secret': env_text,
                   '$class': 'org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl'}}
        client.request(base + 'createCredentials', {'json': json.dumps(payload)}).close()
    else:
        credential = ET.Element('org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl')
        for key, value in {'scope': 'GLOBAL', 'id': CREDENTIAL,
                           'description': MARKER + ': Compose environment', 'secret': env_text}.items():
            ET.SubElement(credential, key).text = value
        client.request(base + f'credential/{CREDENTIAL}/config.xml', ET.tostring(credential), 'application/xml').close()
    print('Compose configuration stored in Jenkins Credentials (no secret printed).')


def prepare(client):
    if command('git', 'status', '--porcelain'):
        raise RuntimeError('Commit or otherwise resolve local changes before exporting an exact source revision.')
    revision = command('git', 'rev-parse', 'HEAD')
    REPORTS.mkdir(parents=True, exist_ok=True)
    bundle = REPORTS / f'{revision}.bundle'
    subprocess.run(['git', 'bundle', 'create', str(bundle), 'HEAD'], cwd=ROOT, check=True)
    command('docker', 'compose', 'exec', '-T', 'jenkins', 'mkdir', '-p', '/var/jenkins_home/local-sources')
    command('docker', 'compose', 'cp', str(bundle), f'jenkins:/var/jenkins_home/local-sources/{revision}.bundle')
    command('docker', 'compose', 'exec', '-T', '--user', '0', 'jenkins', 'chown',
            'jenkins:jenkins', f'/var/jenkins_home/local-sources/{revision}.bundle')
    job_path = f'job/{JOB}/'
    exists = False
    try:
        info = client.get(job_path + 'api/json?tree=description,lastBuild[number,building]')
        if not (info.get('description') or '').startswith(MARKER):
            raise RuntimeError('Refusing to replace a job not managed by this project.')
        if info.get('lastBuild') and info['lastBuild'].get('building'):
            raise RuntimeError('Wait until the current build finishes before updating the job.')
        exists = True
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    root = ET.Element('flow-definition', {'plugin': 'workflow-job'})
    ET.SubElement(root, 'description').text = MARKER + ': committed source via local bundle; no remote push.'
    ET.SubElement(root, 'keepDependencies').text = 'false'
    props = ET.SubElement(root, 'properties')
    defs = ET.SubElement(ET.SubElement(props, 'hudson.model.ParametersDefinitionProperty'), 'parameterDefinitions')
    for name, value in {'SOURCE_MODE': 'LOCAL', 'LOCAL_COMMIT': revision, 'FAULT': 'none'}.items():
        element = ET.SubElement(defs, 'hudson.model.StringParameterDefinition')
        ET.SubElement(element, 'name').text = name
        ET.SubElement(element, 'defaultValue').text = value
    definition = ET.SubElement(root, 'definition', {'class': 'org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition', 'plugin': 'workflow-cps'})
    ET.SubElement(definition, 'script').text = command('git', 'show', f'{revision}:{PIPELINE_FILE}')
    ET.SubElement(definition, 'sandbox').text = 'true'
    ET.SubElement(root, 'disabled').text = 'false'
    endpoint = job_path + 'config.xml' if exists else 'createItem?name=' + JOB
    client.request(endpoint, ET.tostring(root), 'application/xml').close()
    print(f'Prepared {JOB} at exact local commit {revision}; nothing pushed to GitHub.')
    return revision


def api_state():
    container = command('docker', 'compose', 'ps', '-q', 'api')
    if not container:
        return {'container': '', 'image': ''}
    image = command('docker', 'inspect', '--format', '{{.Image}}', container)
    return {'container': container, 'image': image}


def run(client, fault):
    revision = prepare(client)
    before = api_state()
    with client.request(f'job/{JOB}/buildWithParameters',
                        {'SOURCE_MODE': 'LOCAL', 'LOCAL_COMMIT': revision, 'FAULT': fault}) as response:
        queue_path = urllib.parse.urlsplit(response.headers['Location']).path
    for _ in range(30):
        info = client.get(queue_path + 'api/json')
        if info.get('cancelled'):
            raise RuntimeError('Build queue item was cancelled.')
        if 'executable' in info:
            number = info['executable']['number']
            state = {'number': number, 'commit': revision, 'fault': fault, 'before': before}
            (REPORTS / f'build-{number}.json').write_text(json.dumps(state, indent=2))
            print(f'Build #{number} started: {client.url}/job/{JOB}/{number}/ (fault={fault})')
            return
        time.sleep(1)
    raise RuntimeError('Build is queued but has not started; inspect Jenkins executors.')


def collect(client, number, verify=False):
    info = client.get(f'job/{JOB}/{number}/api/json?tree=number,building,result,url,artifacts[fileName,relativePath]')
    print(json.dumps(info, indent=2))
    if info['building']:
        if verify:
            raise RuntimeError('Build is still running; verification cannot pass yet.')
        return
    directory = REPORTS / f'build-{number}'
    directory.mkdir(exist_ok=True)
    with client.request(f'job/{JOB}/{number}/consoleText') as response:
        log = response.read().decode(errors='replace')
    # Local evidence also redacts known values, independently of Jenkins masking.
    secret_values = [json.loads(SECRET.read_text())['token']]
    for line in (ROOT / '.env').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            if any(word in key for word in ('PASSWORD', 'TOKEN', 'SECRET')) and value:
                secret_values.append(value)
    for value in secret_values:
        log = log.replace(value, '***REDACTED***')
    (directory / 'console.log').write_text(log, encoding='utf-8')
    for artifact in info['artifacts']:
        relative = artifact['relativePath']
        if Path(relative).name != artifact['fileName']:
            raise RuntimeError('Unexpected artifact path')
        with client.request(f'job/{JOB}/{number}/artifact/' + urllib.parse.quote(relative)) as response:
            (directory / artifact['fileName']).write_bytes(response.read())
    if not verify:
        return
    record = json.loads((REPORTS / f'build-{number}.json').read_text())
    fault = record['fault']
    after = api_state()
    expected = 'SUCCESS' if fault == 'none' else 'FAILURE'
    assert info['result'] == expected, f"Expected {expected}; inspect {directory / 'console.log'}"
    assert (directory / 'source-commit.txt').read_text().strip() == record['commit']
    junit = ET.parse(directory / 'pytest.xml')
    cases = junit.findall('.//testcase')
    failed = [case for case in cases if case.find('failure') is not None or case.find('error') is not None]
    assert cases, 'No test cases were reported'
    if fault == 'pytest':
        assert len(failed) == 1 and failed[0].get('name') == 'test_expected_failure_for_pipeline_gate'
    else:
        assert not failed, 'Pytest failed before the intended validation point'
    if fault in ('candidate-smoke', 'post-deploy'):
        assert 'HTTP Error 404' in log, 'The expected HTTP failure did not execute'
    if fault in ('pytest', 'candidate-smoke'):
        assert after == record['before'], 'A rejected candidate changed the deployed API'
        assert not (directory / 'deployment.txt').exists()
    elif fault == 'post-deploy':
        assert after['image'] == record['before']['image'], 'Rollback did not restore previous image'
        assert (directory / 'rollback.txt').is_file()
        assert not (directory / 'deployment.txt').exists()
    else:
        assert (directory / 'deployment.txt').is_file()
        revision = command('docker', 'inspect', '--format', '{{index .Config.Labels "org.opencontainers.image.revision"}}', after['container'])
        assert revision == record['commit']
    record.update(result=info['result'], after=after, verified=True)
    (REPORTS / f'build-{number}.json').write_text(json.dumps(record, indent=2))
    print(f'PASS: build #{number}, {fault}, expected result and deployment state verified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('setup')
    sub.add_parser('prepare')
    run_parser = sub.add_parser('run')
    run_parser.add_argument('--fault', choices=['none', 'pytest', 'candidate-smoke', 'post-deploy'], default='none')
    for name in ('status', 'verify'):
        sub.add_parser(name).add_argument('number', type=int)
    args = parser.parse_args()
    client = connect()
    if args.action == 'setup':
        configure_credential(client)
    elif args.action == 'prepare':
        prepare(client)
    elif args.action == 'run':
        run(client, args.fault)
    else:
        collect(client, args.number, verify=args.action == 'verify')


if __name__ == '__main__':
    main()

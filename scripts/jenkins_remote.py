"""Configure real private GitHub checkout and a restricted HTTPS webhook, without publishing code."""
import argparse
import base64
import getpass
import json
from pathlib import Path
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET

from jenkins_local import ROOT, Jenkins, connect, configure_credential, api_state
from jenkins_ingestion import credential as configure_kaggle

REPO='DavierGonz/ParcialBigData'
MARKER='Managed by ParcialBigData final CI'
SSH_ID='parcialbigdata-github-readonly'
HOOK_ID='parcialbigdata-webhook-secret'
STATE=ROOT/'secrets/github-integration.json'
COMPOSE=['docker','compose','-f','docker-compose.yml','-f','ci/compose.webhook.yml']


def gh(path,payload=None,method=None):
    args=['gh','api',path]
    if method:args+=['--method',method]
    if payload is not None:args+=['--input','-']
    result=subprocess.run(args,cwd=ROOT,input=None if payload is None else json.dumps(payload),text=True,capture_output=True,check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def groovy(client,script):
    with client.request('scriptText',{'script':script}) as response:body=response.read().decode()
    if 'CONFIGURED' not in body:raise RuntimeError('Jenkins configuration failed (response withheld to protect credentials).')


def install_credentials(client):
    directory=ROOT/'secrets';directory.mkdir(exist_ok=True)
    key=directory/'github-readonly'
    if not key.exists():
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','ParcialBigData Jenkins readonly','-f',str(key)],check=True)
    public=key.with_suffix('.pub').read_text().strip()
    keys=gh(f'repos/{REPO}/keys')
    existing=next((k for k in keys if k['key'].split()[:2]==public.split()[:2]),None)
    if existing:
        if not existing['read_only']:raise RuntimeError('Existing deploy key is not read-only')
    else:gh(f'repos/{REPO}/keys',{'title':'ParcialBigData Jenkins readonly','key':public,'read_only':True})
    hook=directory/'webhook-secret.txt'
    if not hook.exists():hook.write_text(secrets.token_hex(32),encoding='ascii')
    payload={'private':key.read_text(),'webhook':hook.read_text().strip()}
    encoded=base64.b64encode(json.dumps(payload).encode()).decode()
    groovy(client,"""
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.Domain
import com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl
import hudson.util.Secret
def payload=new groovy.json.JsonSlurper().parseText(new String('"""+encoded+"""'.decodeBase64(),'UTF-8'))
def store=SystemCredentialsProvider.getInstance().getStore()
def domain=Domain.global()
def creds=[new BasicSSHUserPrivateKey(CredentialsScope.GLOBAL,'parcialbigdata-github-readonly','git',new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource(payload.private),'','Managed by ParcialBigData final CI: readonly deploy key'),new StringCredentialsImpl(CredentialsScope.GLOBAL,'parcialbigdata-webhook-secret','Managed by ParcialBigData final CI: HMAC',Secret.fromString(payload.webhook))]
creds.each { value ->
 def old=store.getCredentials(domain).find { it.id==value.id }
 if(old && !old.description.startsWith('Managed by ParcialBigData final CI')) throw new IllegalStateException('Unmanaged credential')
 if(old) store.updateCredentials(domain,old,value) else store.addCredentials(domain,value)
}
def config=jenkins.model.Jenkins.get().getDescriptorByType(org.jenkinsci.plugins.github.config.GitHubPluginConfig)
config.setHookSecretConfig(new org.jenkinsci.plugins.github.config.HookSecretConfig('parcialbigdata-webhook-secret'))
config.save()
println('CONFIGURED')
""")
    # Host keys come from GitHub's authenticated HTTPS API, not an unverified ssh-keyscan.
    host_keys=gh('meta')['ssh_keys']
    known=''.join('github.com '+k+'\n' for k in host_keys)
    subprocess.run(['docker','compose','exec','-T','jenkins','sh','-c','umask 077; mkdir -p /var/jenkins_home/.ssh; cat > /var/jenkins_home/.ssh/known_hosts'],input=known,text=True,check=True,cwd=ROOT)
    configure_credential(client);configure_kaggle(client)
    print('Read-only deploy key, verified GitHub host keys and Jenkins credentials configured; no secrets displayed.')


def configure_job(client,name,branch,ingestion=False,script=None):
    try:
        info=client.get(f'job/{name}/api/json?tree=description,lastBuild[building]')
        if not (info.get('description') or '').startswith(MARKER):raise RuntimeError('Refusing unmanaged job')
        if (info.get('lastBuild') or {}).get('building'):raise RuntimeError('Job is running')
        exists=True
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        exists=False
    root=ET.Element('flow-definition',{'plugin':'workflow-job'})
    ET.SubElement(root,'description').text=MARKER+': '+branch
    ET.SubElement(root,'keepDependencies').text='false'
    props=ET.SubElement(root,'properties')
    project=ET.SubElement(props,'com.coravy.hudson.plugins.github.GithubProjectProperty')
    ET.SubElement(project,'projectUrl').text='https://github.com/'+REPO+'/'
    defs=ET.SubElement(ET.SubElement(props,'hudson.model.ParametersDefinitionProperty'),'parameterDefinitions')
    parameters=[('VALIDATE_ONLY','false','Boolean'),('FORCE_ETL','false','Boolean')] if ingestion else [('FAULT','none','String')]
    for key,value,kind in parameters:
        definition=ET.SubElement(defs,f'hudson.model.{kind}ParameterDefinition')
        ET.SubElement(definition,'name').text=key;ET.SubElement(definition,'defaultValue').text=value
    if not ingestion and script is None:
        triggers=ET.SubElement(ET.SubElement(props,'org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty'),'triggers')
        ET.SubElement(ET.SubElement(triggers,'com.cloudbees.jenkins.GitHubPushTrigger'),'spec').text=''
    definition=ET.SubElement(root,'definition',{'class':'org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition' if script is None else 'org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition','plugin':'workflow-cps'})
    if script is None:
        scm=ET.SubElement(definition,'scm',{'class':'hudson.plugins.git.GitSCM','plugin':'git'})
        ET.SubElement(scm,'configVersion').text='2'
        remote=ET.SubElement(ET.SubElement(scm,'userRemoteConfigs'),'hudson.plugins.git.UserRemoteConfig')
        ET.SubElement(remote,'url').text='git@github.com:'+REPO+'.git';ET.SubElement(remote,'credentialsId').text=SSH_ID
        spec=ET.SubElement(ET.SubElement(scm,'branches'),'hudson.plugins.git.BranchSpec');ET.SubElement(spec,'name').text='*/'+branch
        ET.SubElement(scm,'doGenerateSubmoduleConfigurations').text='false';ET.SubElement(scm,'submoduleCfg',{'class':'empty-list'});ET.SubElement(scm,'extensions')
        ET.SubElement(definition,'scriptPath').text='ci/Jenkinsfile.ingestion' if ingestion else 'Jenkinsfile'
        ET.SubElement(definition,'lightweight').text='true'
    else:
        ET.SubElement(definition,'script').text=script;ET.SubElement(definition,'sandbox').text='true'
    ET.SubElement(root,'disabled').text='false'
    client.request(f'job/{name}/config.xml' if exists else 'createItem?name='+name,ET.tostring(root),'application/xml').close()


def webhook():
    raw=subprocess.check_output(COMPOSE+['logs','--no-color','tunnel'],cwd=ROOT,text=True,stderr=subprocess.STDOUT)
    urls=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',raw)
    if not urls:raise RuntimeError('Tunnel URL not ready; run setup-webhook again after checking tunnel logs.')
    url=urls[-1]+'/github-webhook/'
    data={'name':'web','active':True,'events':['push'],'config':{'url':url,'content_type':'json','secret':(ROOT/'secrets/webhook-secret.txt').read_text().strip(),'insecure_ssl':'0'}}
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get('hook_id'):
        result=gh(f"repos/{REPO}/hooks/{state['hook_id']}",data,'PATCH')
    else:result=gh(f'repos/{REPO}/hooks',data)
    STATE.write_text(json.dumps({'hook_id':result['id'],'url':url},indent=2))
    print(json.dumps({'hook_id':result['id'],'url':url,'tls_verification':True,'signature':'HMAC-SHA256'}))


def run(client,job,fault='none',validate_only=False):
    if fault!='none' and not job.startswith('parcialbigdata-validation'):raise ValueError('Faults require validation job')
    before=api_state()
    with client.request(f'job/{job}/buildWithParameters',{'FAULT':fault,'VALIDATE_ONLY':str(validate_only).lower(),'FORCE_ETL':'false'}) as response:
        queue=urllib.parse.urlsplit(response.headers['Location']).path
    for _ in range(40):
        value=client.get(queue+'api/json')
        if 'executable' in value:
            n=value['executable']['number'];folder=ROOT/'reports/final'/job;folder.mkdir(parents=True,exist_ok=True)
            (folder/f'{n}-before.json').write_text(json.dumps({'before':before,'fault':fault},indent=2))
            print(f'{client.url}/job/{job}/{n}/');return
        time.sleep(1)
    raise RuntimeError('Build remains queued')


def status(client,job,number):
    info=client.get(f'job/{job}/{number}/api/json?tree=number,building,result,duration,url,actions[causes[shortDescription]],artifacts[fileName,relativePath]')
    print(json.dumps(info,indent=2))
    if info['building']:return
    folder=ROOT/'reports/final'/job/str(number);folder.mkdir(parents=True,exist_ok=True)
    (folder/'build.json').write_text(json.dumps(info,indent=2))
    for item in info['artifacts']:
        if Path(item['relativePath']).name!=item['fileName']:raise RuntimeError('Unexpected artifact path')
        with client.request(f'job/{job}/{number}/artifact/'+urllib.parse.quote(item['relativePath'])) as response:(folder/item['fileName']).write_bytes(response.read())
    # Console stays in authenticated Jenkins. Do not export potentially sensitive logs by default.


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['setup','setup-webhook','run','status','login'])
    p.add_argument('--job',default='parcialbigdata-validation');p.add_argument('--number',type=int)
    p.add_argument('--fault',choices=['none','pytest','candidate-smoke','post-deploy'],default='none');p.add_argument('--validate-only',action='store_true')
    args=p.parse_args()
    if args.action=='login':
        username=input('Jenkins username: ');password=getpass.getpass('Jenkins password or API token: ');client=Jenkins(username,password)
        with client.request('me/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken',{'newTokenName':'parcialbigdata-final-ci'}) as response:token=json.load(response)['data']['tokenValue']
        (ROOT/'secrets').mkdir(exist_ok=True);(ROOT/'secrets/jenkins-local-api.json').write_text(json.dumps({'username':username,'token':token,'url':client.url}))
        print('API token saved only in ignored secrets/.');return
    if args.action=='setup-webhook':webhook();return
    client=connect()
    if args.action=='setup':
        install_credentials(client)
        configure_job(client,'parcialbigdata-main','main')
        configure_job(client,'parcialbigdata-validation','develop/final-delivery')
        configure_job(client,'parcialbigdata-ingestion','develop/final-delivery',ingestion=True)
        print('Remote SCM jobs configured. No code pushed and no build triggered.')
    elif args.action=='run':run(client,args.job,args.fault,args.validate_only)
    else:status(client,args.job,args.number)


if __name__=='__main__':main()

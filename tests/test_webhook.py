import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock

import pytest

from webhook import create_app


@pytest.fixture
def client(tmp_path):
    secret=tmp_path/'secret';secret.write_text('fixture-only-secret')
    app=create_app({'TESTING':True,'SECRET_FILE':str(secret),'RECEIPTS':str(tmp_path/'receipts.sqlite')})
    return app.test_client()


def send(client,ref='refs/heads/main',event='push',signature=True,repository='DavierGonz/ParcialBigData',delivery='fixture-1'):
    body=json.dumps({'repository':{'full_name':repository},'ref':ref,'after':'a'*40}).encode()
    headers={'Content-Type':'application/json','X-GitHub-Event':event,'X-GitHub-Delivery':delivery}
    if signature:headers['X-Hub-Signature-256']='sha256='+hmac.new(b'fixture-only-secret',body,hashlib.sha256).hexdigest()
    return client.post('/github-webhook/',data=body,headers=headers)


def test_signature_and_administration_are_protected(client):
    assert send(client,signature=False).status_code==403
    assert send(client,repository='other/repo').status_code==403
    assert client.get('/login').status_code==404
    assert client.post('/scriptText').status_code==404
    assert client.get('/github-webhook/').status_code==405
    assert client.post('/github-webhook/',data=b'x'*(512*1024+1)).status_code==413


@pytest.mark.parametrize('ref',['refs/heads/main','refs/heads/develop/final-delivery'])
def test_allowed_push_and_persistent_deduplication(client,ref):
    response=MagicMock();response.__enter__.return_value.status=200
    with patch('webhook.urlopen',return_value=response) as forward:
        assert send(client,ref=ref).json['status']=='forwarded'
        assert send(client,ref=ref).json['status']=='duplicate'
        assert forward.call_count==1


def test_ping_other_events_and_unavailable_jenkins(client):
    from urllib.error import URLError
    assert send(client,event='ping').json['status']=='pong'
    assert send(client,event='pull_request').status_code==202
    assert send(client,ref='refs/heads/untrusted').status_code==202
    with patch('webhook.urlopen',side_effect=URLError('unavailable')):
        assert send(client).status_code==502
        assert send(client).status_code==502  # failure is not marked delivered

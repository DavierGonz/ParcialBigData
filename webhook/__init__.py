"""Restricted GitHub webhook gateway; the Jenkins administration UI is never proxied."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

from flask import Flask, jsonify, request


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=512*1024, SECRET_FILE='/run/secrets/webhook_secret',
                      RECEIPTS='/state/deliveries.sqlite', JENKINS_URL='http://jenkins:8080/github-webhook/',
                      REPOSITORY='DavierGonz/ParcialBigData',
                      ALLOWED_REFS={'refs/heads/main','refs/heads/develop/final-delivery'})
    if config: app.config.update(config)

    @app.get('/health')
    def health(): return jsonify(status='ok')

    @app.post('/github-webhook/')
    def receive():
        body = request.get_data()
        secret = Path(app.config['SECRET_FILE']).read_bytes().strip()
        expected = 'sha256='+hmac.new(secret,body,hashlib.sha256).hexdigest()
        if not secret or not hmac.compare_digest(request.headers.get('X-Hub-Signature-256',''),expected):
            return jsonify(error='Invalid signature'),403
        if not request.is_json: return jsonify(error='JSON required'),415
        payload = request.get_json(silent=True)
        if not isinstance(payload,dict): return jsonify(error='Invalid JSON'),400
        repository = payload.get('repository')
        if not isinstance(repository,dict) or repository.get('full_name')!=app.config['REPOSITORY']:
            return jsonify(error='Repository not allowed'),403
        event = request.headers.get('X-GitHub-Event','')
        delivery = request.headers.get('X-GitHub-Delivery','')
        if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}',delivery): return jsonify(error='Invalid delivery ID'),400
        if event=='ping': return jsonify(status='pong',delivery=delivery)
        if event!='push' or payload.get('ref') not in app.config['ALLOWED_REFS'] or payload.get('deleted'):
            return jsonify(status='ignored',delivery=delivery),202
        if not re.fullmatch('[0-9a-f]{40}',str(payload.get('after',''))): return jsonify(error='Invalid revision'),400
        # A successful GitHub delivery is forwarded once, even after receiver restarts.
        with sqlite3.connect(app.config['RECEIPTS'],timeout=10) as db:
            db.execute('CREATE TABLE IF NOT EXISTS receipts (delivery TEXT PRIMARY KEY, received REAL)')
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM receipts WHERE delivery=?',(delivery,)).fetchone():
                return jsonify(status='duplicate',delivery=delivery)
            try:
                headers={key:request.headers[key] for key in ('X-Hub-Signature-256','X-GitHub-Event','X-GitHub-Delivery')}
                headers['Content-Type']='application/json'
                with urlopen(Request(app.config['JENKINS_URL'],data=body,headers=headers),timeout=15) as response:
                    if response.status!=200: raise URLError('Jenkins rejected delivery')
            except URLError:
                return jsonify(error='Jenkins unavailable; redeliver event'),502
            db.execute('INSERT INTO receipts VALUES (?,?)',(delivery,time.time()))
            db.execute('DELETE FROM receipts WHERE received < ?',(time.time()-30*86400,))
            db.commit()
        app.logger.warning('Forwarded delivery=%s ref=%s revision=%s',delivery,payload['ref'],payload['after'])
        return jsonify(status='forwarded',delivery=delivery)

    @app.errorhandler(413)
    def too_large(error): return jsonify(error='Payload too large'),413

    return app

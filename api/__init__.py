"""Minimal service for phase one."""

from flask import Flask, jsonify


def create_app(test_config=None):
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)

    @app.get('/health')
    def health():
        # Liveness only; cluster readiness is checked by verify_infra.py.
        return jsonify(status='ok', service='us-accidents-api'), 200

    return app

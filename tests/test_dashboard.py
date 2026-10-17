"""The web shell is available without MongoDB and keeps the JSON API contract."""
import pytest
from api import create_app, repository


@pytest.fixture
def client(monkeypatch):
    def unexpected_database():
        raise AssertionError('Rendering the UI must not query MongoDB')
    monkeypatch.setattr(repository, 'database', unexpected_database)
    return create_app({'TESTING': True}).test_client()


def test_dashboard_is_html_and_database_independent(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.mimetype == 'text/html'
    assert '<html lang="es">' in response.text
    assert 'Explora los accidentes de tránsito' in response.text
    assert 'Define tu búsqueda' in response.text
    for value in ['id="map"', 'id="query-form"', 'id="radius-slider"', 'id="result-count"', 'id="overview-button"']:
        assert value in response.text
    for retired in ['id="temporal-chart"', 'id="guide-dialog"', 'id="mode-polygon"', 'id="hotspots-toggle"', 'class="metrics"', 'data-view=']:
        assert retired not in response.text
    assert '1.103.657' not in response.text
    assert response.headers['Cache-Control'] == 'no-cache'


def test_dashboard_security_policy_and_existing_health(client):
    response = client.get('/')
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert client.get('/health').json == {'status': 'ok', 'service': 'us-accidents-api'}
    assert client.post('/').status_code == 405


@pytest.mark.parametrize('asset,mimetype', [
    ('dashboard.js', 'javascript'), ('dashboard.css', 'text/css'),
    ('brand.svg', 'image/svg+xml'), ('vendor/leaflet/leaflet.js', 'javascript'),
    ('vendor/leaflet/leaflet.css', 'text/css'), ('us-outline.geojson', 'json'),
])
def test_assets_are_bundled_and_available(client, asset, mimetype):
    response = client.get('/static/' + asset)
    assert response.status_code == 200
    # GeoJSON can use application/geo+json or application/geojson on Windows/Linux.
    if asset.endswith('.geojson'):
        import json
        assert json.loads(response.data)['features'][0]['properties']['name'] == 'Estados Unidos'
    else:
        assert mimetype in response.content_type


def test_no_secret_configuration_is_served(client):
    for path in ['/static/.env', '/static/secrets/jenkins-local-api.json', '/.env']:
        assert client.get(path).status_code == 404

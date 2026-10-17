"""Read-only HTTP verification of the Flask dashboard and its bundled assets."""
import argparse
import json
from urllib.request import urlopen


def verify(base_url):
    def get(path):
        with urlopen(base_url.rstrip('/') + path, timeout=10) as response:
            assert response.status == 200
            return response.read().decode()
    html = get('/')
    assert '<html lang="es">' in html and 'id="map"' in html and 'id="query-form"' in html
    assert '1.103.657' not in html
    for path in ['/static/dashboard.js', '/static/dashboard.css', '/static/vendor/leaflet/leaflet.js', '/static/vendor/leaflet/leaflet.css']:
        assert len(get(path)) > 500
    outline = json.loads(get('/static/us-outline.geojson'))
    assert outline['features'][0]['properties']['name'] == 'Estados Unidos'
    print('PASS: dashboard HTML, bundled assets and local US outline')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url', nargs='?', default='http://127.0.0.1:5000')
    verify(parser.parse_args().base_url)

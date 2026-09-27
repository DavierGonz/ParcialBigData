import pytest

from api import create_app


@pytest.fixture
def client():
    return create_app({'TESTING': True}).test_client()


def test_health_contract(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert response.get_json() == {'status': 'ok', 'service': 'us-accidents-api'}


def test_health_is_available_without_database_configuration(client, monkeypatch):
    monkeypatch.delenv('MONGO_URI', raising=False)
    assert client.get('/health').status_code == 200


def test_health_rejects_post(client):
    assert client.post('/health').status_code == 405


def test_unknown_route(client):
    assert client.get('/missing-route').status_code == 404

def test_index(test_client):
    response = test_client.get('/')
    assert response.status_code == 200


def test_heartbeat(test_client):
    response = test_client.get('/heartbeat')
    assert response.status_code == 200
    assert b"OK" in response.data


def test_ping(test_client):
    response = test_client.get('/ping')
    assert response.status_code == 200
    assert b"pong" in response.data

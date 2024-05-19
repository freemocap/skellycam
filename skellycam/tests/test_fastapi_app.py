from starlette.testclient import TestClient


def test_app(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200

    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/redoc")
    assert response.status_code == 200



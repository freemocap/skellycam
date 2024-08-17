from starlette.testclient import TestClient

from skellycam.api import HELLO_FROM_SKELLYCAM_BACKEND_MESSAGE


def test_app(client_fixture: TestClient) -> None:
    response = client_fixture.get("/")
    assert response.status_code == 200

    response = client_fixture.get("/docs")
    assert response.status_code == 200

    response = client_fixture.get("/redoc")
    assert response.status_code == 200


def test_app_hello(client_fixture: TestClient) -> None:
    response = client_fixture.get("/hello")
    assert response.status_code == 200
    assert response.json() == HELLO_FROM_SKELLYCAM_BACKEND_MESSAGE

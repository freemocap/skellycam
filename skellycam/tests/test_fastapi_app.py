import multiprocessing

import pytest
from fastapi.testclient import TestClient

from skellycam.backend.api_server.fastapi_app import FastApiApp


@pytest.fixture
def ready_event() -> multiprocessing.Event:
    return multiprocessing.Event()


@pytest.fixture
def shutdown_event() -> multiprocessing.Event:
    return multiprocessing.Event()


@pytest.fixture
def app_instance(
    ready_event: multiprocessing.Event, shutdown_event: multiprocessing.Event
) -> FastApiApp:
    return FastApiApp(ready_event, shutdown_event, timeout=5)


@pytest.fixture
def client(app_instance: FastApiApp) -> TestClient:
    return TestClient(app_instance.app)


def test_root_redirects_to_docs(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_custom_swagger_ui(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200

from starlette.testclient import TestClient

from skellycam.api.app_factory import create_app


def test_app() -> None:
    app = create_app()
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    client.close()
    del app

def test_websocket() -> None:
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/connect") as websocket:
        data = websocket.receive_text()
        assert data == "👋Hello, client!"
        websocket.send_text("test")
    client.close()
    del app

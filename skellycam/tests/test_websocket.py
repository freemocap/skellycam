from starlette.testclient import TestClient

from skellycam.api.routes.websocket.websocket_server import HELLO_CLIENT_MESSAGE


def test_websocket_connection(client: TestClient) -> None:
    with client.websocket_connect("/ws/connect") as websocket:
        data = websocket.receive_text()
        assert data == HELLO_CLIENT_MESSAGE


def test_websocket_send_and_receive(client: TestClient) -> None:
    with client.websocket_connect("/ws/connect") as websocket:
        data = websocket.receive_text()
        assert data == HELLO_CLIENT_MESSAGE  # Assuming the server echoes this back
        websocket.send_text("Hello, server!")




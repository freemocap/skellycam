from starlette.testclient import TestClient

from skellycam.api import HELLO_CLIENT_TEXT_MESSAGE, HELLO_CLIENT_BYTES_MESSAGE


def test_websocket_connection(client_fixture: TestClient) -> None:
    with client_fixture.websocket_connect("/ws/connect") as websocket:
        data = websocket.receive_text()
        assert data == HELLO_CLIENT_TEXT_MESSAGE


def test_websocket_send_and_receive(client_fixture: TestClient) -> None:
    with client_fixture.websocket_connect("/ws/connect") as websocket:
        data = websocket.receive_text()
        assert data == HELLO_CLIENT_TEXT_MESSAGE  # Assuming the server echoes this back
        websocket.send_text("Hello, server!")
        bytes_data = websocket.receive_bytes()
        assert bytes_data == HELLO_CLIENT_BYTES_MESSAGE

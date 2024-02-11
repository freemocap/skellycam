import sys

import uvicorn
from PySide6.QtCore import QUrl
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication, QPushButton
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.websockets import WebSocket

from skellycam.backend.system.environment.get_logger import logger


class SimpleFastApiWebSocketApp:
    def __init__(self):
        self.app = FastAPI()
        self._register_routes()

    def _register_routes(self):
        @self.app.get("/")
        async def read_root():
            return RedirectResponse("/docs")

        @self.app.websocket("/websocket")
        async def websocket_route(websocket: WebSocket):
            logger.info("WebSocket connection received")
            await websocket.accept()
            while True:
                data = await websocket.receive_bytes()
                logger.info(f"Data received: {data}")
                response_message = f"received bytes: {data}"
                await websocket.send_bytes(bytes(response_message, "utf-8"))


class SimpleWebSocketClient:
    def __init__(self, url: str):
        self.url = QUrl(url)
        self.websocket = QWebSocket()
        self.websocket.connected.connect(self.on_connected)
        self.websocket.binaryMessageReceived.connect(self.on_binary_message_received)
        self.connect_to_server()

    def connect_to_server(self):
        print("Connecting to websocket server")
        self.websocket.open(self.url)

    def on_connected(self):
        print("WebSocket connected")
        self.send_ping()

    def send_ping(self):
        print("Sending ping to server")
        self.websocket.sendBinaryMessage(b"ping")

    def on_binary_message_received(self, message):
        print(f"Received binary message: {message}")


def run_websocket_client():
    print("Running websocket client")
    client = SimpleWebSocketClient()
    client.connect_to_server()
    client.send_ping()


def run_fastapi_app(host: str = "localhost", port: int = 8000):
    print("Running FastAPI app")
    app = SimpleFastApiWebSocketApp().app
    print("Starting Uvicorn server...")
    uvicorn.run(app, host=host, port=port, log_level="debug")


class SimpleApp(QApplication):
    def __init__(self, ws_url: str):
        super().__init__()
        self.client = SimpleWebSocketClient(ws_url)
        self.main_window = QPushButton("Send Ping")
        self.main_window.clicked.connect(self.client.send_ping)
        self.main_window.show()


if __name__ == "__main__":
    import multiprocessing

    host = "localhost"
    port = 8000
    fastapi_process = multiprocessing.Process(target=run_fastapi_app, args=(host, port))

    print("Starting processes...")
    fastapi_process.start()
    ws_url_outer = f"ws://{host}:{port}/websocket"
    app = SimpleApp(ws_url_outer)
    app.exec()

    print("Done!")

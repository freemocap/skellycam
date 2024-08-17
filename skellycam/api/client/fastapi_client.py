import logging
import time

from skellycam.api.client.http_client import HTTPClient
from skellycam.api.client.websocket_client import WebSocketClient
from skellycam.api.server.run_server import APP_URL

logger = logging.getLogger(__name__)


class FastAPIClient:
    def __init__(self, base_url: str = APP_URL):
        self.http_client = HTTPClient(base_url)
        self.ws_client = WebSocketClient(base_url)

    def close(self) -> None:
        self.http_client.close()
        self.ws_client.close()


# Example usage
if __name__ == "__main__":
    client = FastAPIClient()

    try:
        # Example GET request
        future_response = client.http_client.get("/hello")
        response = future_response.result()
        print(response.json())

        # Start WebSocket connection
        client.ws_client.start_websocket()
        time.sleep(5)
    finally:
        client.close()

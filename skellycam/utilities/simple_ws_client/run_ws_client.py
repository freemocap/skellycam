import asyncio
import logging
import multiprocessing

from setproctitle import setproctitle
from tenacity import RetryError

from skellycam.utilities.simple_ws_client.websocket_client import websocket_client

logger = logging.getLogger(__name__)


def run_client(uri: str):
    try:
        asyncio.run(websocket_client(uri))
    except RetryError:
        logger.error("Failed to connect after multiple retries.")
    except Exception as e:
        logger.error(f"An error occurred when running the websocket client: {type(e).__name__} - {e}")


def start_websocket_client():
    logger.info("Starting websocket client...")
    server_uri = "ws://localhost:8003/ws/connect"
    client_process = multiprocessing.Process(target=run_client, args=(server_uri,))
    client_process.start()
    client_process.join()
    logger.info("Websocket client finished")


if __name__ == "__main__":
    process_name = f"Websocket Client"
    setproctitle(process_name)
    start_websocket_client()
    logger.info("Done!")
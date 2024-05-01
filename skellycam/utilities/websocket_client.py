import asyncio
import multiprocessing

import websockets
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError

from skellycam import configure_logging

configure_logging()
import logging

logger = logging.getLogger(__name__)

RETRY_DELAY = 1  # seconds
MAX_RETRIES = 5


@retry(wait=wait_fixed(RETRY_DELAY), stop=stop_after_attempt(MAX_RETRIES), reraise=True)
async def websocket_client(uri: str):
    logger.info(f"Attempting to connect to websocket server at {uri}...")
    async with websockets.connect(uri) as websocket:
        logger.success("Connected to websocket server!")
        await websocket.send("Hello, server!")
        while True:
            message = await websocket.recv()
            if isinstance(message, str):
                print(f"\n\nReceived text from server: '{message}'\n\n")
            elif isinstance(message, bytes):
                print(f"Received binary data with size: {len(message) / 1024}kb")


def run_client(uri: str):
    try:
        asyncio.run(websocket_client(uri))
    except RetryError as e:
        logger.error("Failed to connect after multiple retries.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


def start_websocket_client():
    logger.info("\n\nStarting websocket client...\n\n")
    server_uri = "ws://localhost:8003/ws/connect"
    client_process = multiprocessing.Process(target=run_client, args=(server_uri,))
    client_process.start()
    client_process.join()
    logger.info("\n\nWebsocket client finished\n\n")


if __name__ == "__main__":
    start_websocket_client()
    logger.info("Done!")

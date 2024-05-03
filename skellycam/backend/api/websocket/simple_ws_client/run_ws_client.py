import asyncio
import multiprocessing

from setproctitle import setproctitle
from tenacity import RetryError

from skellycam import configure_logging
from skellycam.backend.api.websocket.simple_ws_client.websocket_client import websocket_client
from skellycam.system.logging_configuration.log_level_enum import LogLevel

import logging

logger = logging.getLogger(__name__)


def run_client(uri: str):
    try:
        asyncio.run(websocket_client(uri))
    except RetryError as e:
        logger.error("Failed to connect after multiple retries.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


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

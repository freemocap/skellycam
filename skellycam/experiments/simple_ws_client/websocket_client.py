import asyncio

import skellycam.core.memory.shared_memory_demo
import websockets
from skellycam.frontend import SimpleViewer
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log

from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload

RETRY_DELAY = 1  # seconds
MAX_RETRIES = 5

import logging

logger = logging.getLogger(__name__)


async def listen_for_server_messages(websocket: websockets.WebSocketClientProtocol,
                                     quit_event: asyncio.Event):
    viewer = SimpleViewer()
    while not quit_event.is_set():
        message = await websocket.recv()
        if isinstance(message, str):
            logger.info(f"Received text from server: '{message}'")
        elif isinstance(message, bytes):
            if viewer.should_quit:
                logger.info("Viewer quit - Closing client connection...")
                quit_event.set()
                break
            frontend_payload = FrontendFramePayload.from_msgpack(message)
            logger.trace(
                f"Received ws binary message: {len(message) / 1024}kb with images from Cameras [{skellycam.core.memory.shared_memory_demo.camera_ids}]")
            if len(frontend_payload) > 0:
                viewer.display_images(frontend_payload)
    logger.info("`quit_event` set - listener loop has stopped.")


@retry(
    wait=wait_fixed(RETRY_DELAY),
    stop=stop_after_attempt(MAX_RETRIES),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def websocket_client(uri: str, prescribed_framerate: float = 30):
    logger.info(f"Attempting to connect to websocket server at {uri}...")
    viewer = SimpleViewer(prescribed_framerate=prescribed_framerate)
    quit_event = asyncio.Event()
    try:
        async with websockets.connect(uri) as websocket:
            logger.success("Connected to websocket server!")
            await websocket.send("Hello, server!")
            message = await websocket.recv()
            logger.info(f"Initial message from server: '{message}'")
            await  listen_for_server_messages(websocket, quit_event)
    except ConnectionRefusedError:
        raise  # tenacity will catch this and retry
    except websockets.exceptions.ConnectionClosedOK:
        logger.info("Connection to server closed gracefully.")
    except websockets.exceptions.ConnectionClosedError:
        logger.error("Connection to server closed unexpectedly.")
        raise
    except Exception as e:
        logger.error(f"An error occurred: {type(e)}: {e}")
        raise
    finally:
        logger.info("Closing websocket connection...")
        quit_event.set()
        logger.info("Websocket client finished")

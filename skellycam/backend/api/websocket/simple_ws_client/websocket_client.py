import asyncio

import websockets
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log

from skellycam.backend.api.websocket import LATEST_FRAMES_REQUEST, CAMERA_READY_MESSAGE
from skellycam.backend.api.websocket.simple_ws_client.simple_viewer import SimpleViewer
from skellycam.backend.core.frames.frontend_image_payload import FrontendImagePayload

RETRY_DELAY = 1  # seconds
MAX_RETRIES = 5

import logging

logger = logging.getLogger(__name__)


async def request_frames_from_server(websocket: websockets.WebSocketClientProtocol, interval: float,
                                     quit_event: asyncio.Event, cameras_ready_event: asyncio.Event):
    logger.info("Starting frame request loop with interval: {interval}")
    while not quit_event.is_set():
        await asyncio.sleep(interval)
        if cameras_ready_event.is_set():
            logger.trace("Requesting latest frames from server...")
            await websocket.send(LATEST_FRAMES_REQUEST)
        else:
            logger.debug("Cameras not ready yet, skipping frame request...")
            await asyncio.sleep(1)

    logger.info("`quit_event` set - frame request loop has stopped.")


async def listen_for_server_messages(websocket: websockets.WebSocketClientProtocol, quit_event: asyncio.Event, cameras_ready_event: asyncio.Event):
    viewer = SimpleViewer()
    while not quit_event.is_set():
        message = await websocket.recv()
        if isinstance(message, str):
            logger.info(f"Received text from server: '{message}'")
            if message == CAMERA_READY_MESSAGE:
                logger.success("Cameras are ready!")
                cameras_ready_event.set()
        elif isinstance(message, bytes):
            logger.trace(f"Received binary data with size: {len(message) / 1024}kb")
            if viewer.should_quit:
                logger.info("Viewer quit - Closing client connection...")
                quit_event.set()
                break
            jpeg_images = FrontendImagePayload.from_msgpack(message).jpeg_images_by_camera
            viewer.display_images(jpeg_images)
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
    frame_request_interval = 1 / viewer.prescribed_framerate
    quit_event = asyncio.Event()
    cameras_ready_event = asyncio.Event()
    try:
        async with websockets.connect(uri) as websocket:
            logger.success("Connected to websocket server!")
            await websocket.send("Hello, server!")
            message = await websocket.recv()
            logger.info(f"Initial message from server: '{message}'")
            listener_task = listen_for_server_messages(websocket, quit_event, cameras_ready_event)
            frame_request_task = request_frames_from_server(websocket, frame_request_interval, quit_event, cameras_ready_event)
            await asyncio.gather(listener_task, frame_request_task)
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

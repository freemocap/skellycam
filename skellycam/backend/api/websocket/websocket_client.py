import asyncio
import multiprocessing
from typing import Optional, Dict

import cv2
import numpy as np
import websockets
from setproctitle import setproctitle
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError

from skellycam import configure_logging
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frontend_image_payload import FrontendImagePayload

configure_logging()
import logging

logger = logging.getLogger(__name__)

RETRY_DELAY = 1  # seconds
MAX_RETRIES = 5


class ImageStreamViewer:
    def __init__(self):
        self.windows_initialized = False

    def display_images(self, jpeg_images: Dict[CameraId, Optional[bytes]]):
        for camera_id, jpeg_image in jpeg_images.items():
            if not jpeg_image:
                continue

            window_name = f'Camera {camera_id} - Press Q to quit'
            if not self.windows_initialized:
                # Initialize the window for this camera
                cv2.namedWindow(window_name)
                self.windows_initialized = True

            # Display the image
            np_arr = np.frombuffer(jpeg_image, np.uint8)

            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            cv2.imshow(window_name, image)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.quit()

    def quit(self):
        cv2.destroyAllWindows()

@retry(wait=wait_fixed(RETRY_DELAY), stop=stop_after_attempt(MAX_RETRIES), reraise=True)
async def websocket_client(uri: str, view = True):
    logger.info(f"Attempting to connect to websocket server at {uri}...")
    viewer = ImageStreamViewer() if view else None
    async with websockets.connect(uri) as websocket:
        logger.success("Connected to websocket server!")
        await websocket.send("Hello, server!")

        while True:
            message = await websocket.recv()
            if isinstance(message, str):
                logger.info(f"Received text from server: '{message}'")
            elif isinstance(message, bytes):
                logger.debug(f"Received binary data with size: {len(message) / 1024}kb")
                if view:
                    jpeg_images = FrontendImagePayload.from_msgpack(message).jpeg_images_by_camera
                    viewer.display_images(jpeg_images)



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

import base64
import json
import logging

import cv2
import numpy as np
from PySide6.QtCore import QObject, QTimer

from skellycam.frontend.api_client.api_client import ApiClient

logger = logging.getLogger(__name__)

from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient


class FrameRequester(QObject):
    def __init__(
        self,
        websocket_client: FrontendWebsocketClient,
        api_client: ApiClient,
        parent: QObject,
    ):
        super().__init__(parent=parent)
        self.websocket_connection = websocket_client
        self.api_client = api_client
        self.should_continue = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._request_frames)

    def start_request_timer(self, target_frames_per_second: float):
        logger.info(f"FrameRequester starting...")

        interval_ms = 1000 // target_frames_per_second
        self.timer.start(int(interval_ms))

    def stop_requesting(self):
        logger.info("FrameGrabber stopping...")
        self.timer.stop()

    def _request_frames(self):
        logger.trace("Requesting new frames...")
        # self.websocket_connection.request_frames()  # sends a message to the server to request frames, which will be caught by the websocket handler and emitted as a signal
        response = self.api_client.get_latest_frames()
        compressed_payload_str = response.json()
        compressed_payload = json.loads(compressed_payload_str)
        if not compressed_payload:
            return
        for camera_id, base64_image in compressed_payload.items():
            image_bytes = base64.b64decode(base64_image)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if response:
            logger.trace(f"Received {len(response)} frames")

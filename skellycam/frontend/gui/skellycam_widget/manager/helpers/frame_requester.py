import base64
import json
import logging

import cv2
import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from skellycam.frontend.api_client.api_client import ApiClient

logger = logging.getLogger(__name__)


class FrameRequester(QObject):
    # TODO - emit a MultiFramePayload object instead of a dict (after I clean up that bonkers bytes nonsense)
    new_frames_received = Signal(dict)

    def __init__(
        self,
        api_client: ApiClient,
        parent: QObject,
    ):
        super().__init__(parent=parent)
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
        response = self.api_client.get_latest_frames()

        if response:
            logger.trace(f"Received response: {response}")
            compressed_payload_str = response.json()
            if not compressed_payload_str:
                return

            compressed_payload = json.loads(compressed_payload_str)
            new_frames = {}
            for camera_id, base64_image in compressed_payload.items():
                image_bytes = base64.b64decode(base64_image)
                image_array = np.frombuffer(image_bytes, dtype=np.uint8)
                image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                new_frames[camera_id] = image

            self.new_frames_received.emit(new_frames)
            logger.trace(
                f"Emitted new frames with images from cameras {new_frames.keys()}"
            )

        else:
            logger.trace("No frames received for this request.")

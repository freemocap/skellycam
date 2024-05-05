import logging
import time
from typing import Optional

import cv2

from skellycam.backend.core.cameras.config.apply_config import apply_camera_configuration
from skellycam.backend.core.cameras.config.camera_config import CameraConfig
from skellycam.backend.core.cameras.create_cv2_video_capture import create_cv2_capture
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class TriggerCamera:
    def __init__(
            self,
            config: CameraConfig,
    ):
        self._config: CameraConfig = config
        self._cv2_video_capture: Optional[cv2.VideoCapture] = None
        self._frame_number = 0
    @property
    def camera_id(self) -> CameraId:
        return self._config.camera_id

    async def connect(self):
        logger.info(f"Connecting to camera_id: {self.camera_id}")
        self._cv2_video_capture = await create_cv2_capture(self._config)

    async def update_config(self, new_config: CameraConfig) -> CameraConfig:
        logger.info(
            f"Updating config for camera_id: {self.camera_id}  ->  {new_config}"
        )
        self._config = new_config
        if not self._config.use_this_camera:
            self.close()
            return self._config
        else:
            if self._cv2_video_capture is None:
                await self.connect()

        return await apply_camera_configuration(self._cv2_video_capture, self._config)

    def close(self):
        self._cv2_video_capture.release()
        self._cv2_video_capture = None
        logger.debug(f"Camera ID: [{self._config.camera_id}] closed")

    async def get_frame(self) -> Optional[FramePayload]:
        """
        THIS IS WHERE THE MAGIC HAPPENS

        This method is responsible for grabbing the next frame from the camera - it is the point of "transduction"
         when a pattern of environmental energy (i.e. a timeslice of the 2D pattern of light intensity in 3 wavelengths
          within the field of view of the camera ) is absorbed by the camera's sensor and converted into a digital
          representation of that pattern (i.e. a 2D array of pixel values in 3 channels).

        This is the empirical measurement, whereupon all future inference will derive their epistemological grounding.

        This sweet baby must be protected at all costs. Nothing is allowed to block this call (which could result in
        a frame drop)
        """
        pre_read_timestamp = time.perf_counter_ns()
        success, image = self._cv2_video_capture.read()  # THIS, specifically,  IS WHERE THE MAGIC HAPPENS <3
        post_read_timestamp = time.perf_counter_ns()

        if not success or image is None:
            logger.warning(f"Failed to read frame from camera: {self._config.camera_id}")
            return

        self._frame_number += 1
        return FramePayload.create(
            success=success,
            image=cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
            timestamp_ns=post_read_timestamp,
            frame_number=self._frame_number,
            camera_id=CameraId(self._config.camera_id),
            read_duration_ns=post_read_timestamp - pre_read_timestamp,
        )

import logging
from pprint import pprint
from typing import Dict

import cv2
from PySide6.QtMultimedia import QMediaDevices
from pydantic import BaseModel

from skellycam.backend.core.device_detection.camera_device_info import CameraDeviceInfo
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)

DetectedCameras = Dict[CameraId, CameraDeviceInfo]

class CamerasDetectedResponse(BaseModel):
    detected_cameras: DetectedCameras


async def detect_available_cameras() -> CamerasDetectedResponse:
    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()

    cameras = {}
    for camera_number, camera in enumerate(detected_cameras):
        await _check_camera_available(camera_number)
        camera_device_info = CameraDeviceInfo.from_q_camera_device(
            camera_number=camera_number, camera=camera
        )
        cameras[camera_device_info.cv2_port] = camera_device_info

    return CamerasDetectedResponse(detected_cameras=cameras)


async def _check_camera_available(port: int) -> bool:
    logger.debug(f"Checking if camera on port: {port} is available...")
    cap = cv2.VideoCapture(port)
    success, frame = cap.read()
    if not cap.isOpened() or not success or frame is None:
        logger.debug(f"Camera on port: {port} is not available...")
        return False
    logger.debug(f"Camera on port: {port} is available!")
    cap.release()
    return True


if __name__ == "__main__":
    cameras_out = detect_available_cameras()
    pprint(cameras_out.detected_cameras, indent=4)

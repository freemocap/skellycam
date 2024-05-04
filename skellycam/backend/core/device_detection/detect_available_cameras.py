import logging
from pprint import pprint
from typing import Dict

import cv2
from PySide6.QtMultimedia import QMediaDevices

from skellycam.backend.core.device_detection.camera_device_info import CameraDeviceInfo
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)

DetectedCameras = Dict[CameraId, CameraDeviceInfo]

async def detect_available_cameras(check_if_available: bool = False) -> DetectedCameras:
    logger.important("Detecting available cameras...")
    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()

    cameras = {}
    for camera_number, camera in enumerate(detected_cameras):

        if check_if_available:
            await _check_camera_available(camera_number)

        camera_device_info = CameraDeviceInfo.from_q_camera_device(
            camera_number=camera_number, camera=camera
        )
        cameras[camera_device_info.cv2_port] = camera_device_info
    logger.debug(f"Detected cameras: {list(cameras.keys())}")
    return cameras


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
    pprint(cameras_out, indent=4)

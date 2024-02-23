import concurrent
import logging
from concurrent.futures import ThreadPoolExecutor
from pprint import pprint
from typing import Dict

import cv2
from PySide6.QtMultimedia import QMediaDevices
from pydantic import BaseModel

from skellycam.backend.models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.backend.models.cameras.camera_id import CameraId

logger = logging.getLogger(__name__)

DetectedCameras = Dict[CameraId, CameraDeviceInfo]


class CamerasDetectedResponse(BaseModel):
    detected_cameras: DetectedCameras


def detect_available_cameras() -> CamerasDetectedResponse:
    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()
    cameras = {}

    # for camera_number, camera in enumerate(detected_cameras):
    #     if camera.isNull():
    #         continue
    #     if not _check_camera_available(camera_number):
    #         continue
    #
    #     cameras[camera_number] = CameraDeviceInfo.from_q_camera_device(
    #         camera_number=camera_number, camera=camera
    #     )

    with ThreadPoolExecutor(max_workers=len(detected_cameras)) as executor:
        future_camera_checks = {
            executor.submit(_check_camera_available, camera_number): camera_number
            for camera_number, camera in enumerate(detected_cameras)
            if not camera.isNull()
        }

        for future in concurrent.futures.as_completed(future_camera_checks):
            camera_number = future_camera_checks[future]
            if future.result():
                cameras[camera_number] = CameraDeviceInfo.from_q_camera_device(
                    camera_number=camera_number, camera=detected_cameras[camera_number]
                )
    return CamerasDetectedResponse(detected_cameras=cameras)


def _check_camera_available(port: int) -> bool:
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

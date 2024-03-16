import concurrent
import logging
from concurrent.futures import ThreadPoolExecutor
import platform
from pprint import pprint
from typing import Dict, List

import cv2
from PySide6.QtMultimedia import QMediaDevices, QCamera
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

    if platform.system() == "Darwin":
        camera_ports = detect_opencv_ports()
        for camera in detected_cameras:
            if "Virtual" in camera.description():
                detected_cameras.remove(camera)
                camera_ports.pop()  # assumes virtual camera is always last
        if len(camera_ports) != len(detected_cameras):
            raise ValueError("OpenCV and Qt did not detect same number of cameras")
    else:
        camera_ports = range(len(detected_cameras))
    cameras = {}
    for camera_number, camera in zip(camera_ports, detected_cameras):
        try:
            camera_device_info = CameraDeviceInfo.from_q_camera_device(
                camera_number=camera_number, camera=camera
            )
            cameras[camera_device_info.cv2_port] = camera_device_info
        except ValueError:
            logger.warning(f"Could not use camera: {camera_number}")

    # with ThreadPoolExecutor(max_workers=len(detected_cameras)) as executor:
    #     future_camera_checks = {
    #         executor.submit(_check_camera_available, camera_number): camera_number
    #         for camera_number, camera in enumerate(detected_cameras)
    #         if not camera.isNull()
    #     }
    #
    #     for future in concurrent.futures.as_completed(future_camera_checks):
    #         camera_number = future_camera_checks[future]
    #         if future.result():
    #             cameras[camera_number] = CameraDeviceInfo.from_q_camera_device(
    #                 camera_number=camera_number, camera=detected_cameras[camera_number]
    #             )
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

def detect_opencv_ports(max_ports: int = 20, max_unused_ports: int = 5) -> List[int]:
    unused = 0
    i = 0
    ports = []
    while i < max_ports and unused < max_unused_ports:
        if _check_camera_available(i):
            ports.append(i)
        else:
            unused += 1
        i += 1

    return ports


if __name__ == "__main__":
    cameras_out = detect_available_cameras()
    pprint(cameras_out.detected_cameras, indent=4)

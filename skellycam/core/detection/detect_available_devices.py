import logging
import platform
from pprint import pprint
from typing import List, Tuple

import cv2
from PySide6.QtMultimedia import QMediaDevices, QCameraDevice

from skellycam.core.detection.camera_device_info import CameraDeviceInfo, AvailableDevices

logger = logging.getLogger(__name__)


async def detect_available_devices(check_if_available: bool = False) -> AvailableDevices:
    logger.info("Detecting available cameras...")
    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()

    if platform.system() == "Darwin":
        detected_cameras, camera_ports = await order_darwin_cameras(detected_cameras=detected_cameras)
    else:
        camera_ports = range(len(detected_cameras))

    cameras = {}
    for camera_number, camera in zip(camera_ports, detected_cameras):

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

async def order_darwin_cameras(detected_cameras: List[QCameraDevice]) -> Tuple[List[QCameraDevice], List[int]]:
    camera_ports = await detect_opencv_ports()
    for camera in detected_cameras:
        if "Virtual" in camera.description():
            detected_cameras.remove(camera)
            camera_ports.pop()  # assumes virtual camera is always last
    if len(camera_ports) != len(detected_cameras):
        raise ValueError(f"OpenCV and Qt did not detect same number of cameras: {len(camera_ports)} != {len(detected_cameras)}")
    
    return detected_cameras, camera_ports
    

async def detect_opencv_ports(max_ports: int = 20, max_unused_ports: int = 5) -> List[int]:
    unused = 0
    i = 0
    ports = []
    while i < max_ports and unused < max_unused_ports:
        camera_available = await _check_camera_available(i)
        if camera_available:
            ports.append(i)
        else:
            unused += 1
        i += 1

    return ports


if __name__ == "__main__":
    cameras_out = detect_available_devices()
    pprint(cameras_out, indent=4)

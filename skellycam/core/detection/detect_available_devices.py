import logging
import multiprocessing
import platform
from typing import List, Tuple

import cv2
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QCameraDevice

from skellycam.app.app_state import AppState
from skellycam.core.detection.camera_device_info import CameraDeviceInfo, AvailableDevices

logger = logging.getLogger(__name__)


def detect_available_devices(check_if_available: bool = True) -> AvailableDevices:
    from PySide6.QtMultimedia import QMediaDevices
    # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client?
    close_app = False
    # if not QCoreApplication.instance():
    #     logger.debug("No QCoreApplication instance found - creating new instance so we can use QMediaDevices to detect cameras...")
    #     app = QCoreApplication([])
    #     close_app = True
    # else:
    #     app = QCoreApplication.instance()

    try:
        logger.info("Detecting available cameras...")
        devices = QMediaDevices()
        detected_cameras = devices.videoInputs()

        if platform.system() == "Darwin":
            detected_cameras, camera_ports = order_darwin_cameras(detected_cameras=detected_cameras)
        else:
            camera_ports = range(len(detected_cameras))

        camera_devices = {}
        for camera_number, camera in zip(camera_ports, detected_cameras):

            if check_if_available and not platform.system() == "Darwin":  # macOS cameras get checked in order_darwin_cameras
                _check_camera_available(camera_number)

            camera_device_info = CameraDeviceInfo.from_q_camera_device(
                camera_number=camera_number, camera=camera
            )
            camera_devices[camera_device_info.cv2_port] = camera_device_info
        logger.debug(f"Detected camera_devices: {list(camera_devices.keys())}")
        return camera_devices
    except Exception as e:
        logger.exception(f"Error detecting available cameras: {e}")
        raise


def order_darwin_cameras(detected_cameras: List[QCameraDevice]) -> Tuple[List[QCameraDevice], List[int]]:
    """
    Reorder QMultiMediaDevices to match order of OpenCV ports on macOS. 

    Removes virtual cameras, and assumes virtual cameras are always last. 
    Also assumes that once virtual cameras are removed, the order of the cameras from Qt will match the order of OpenCV.
    """
    camera_ports = detect_opencv_ports()
    for camera in detected_cameras:
        if "virtual" in camera.description().lower():
            detected_cameras.remove(camera)
            camera_ports.pop()  # assumes virtual camera is always last # TODO - not this lol
    if len(camera_ports) != len(detected_cameras):
        raise ValueError(
            f"OpenCV and Qt did not detect same number of cameras: OpenCV: {len(camera_ports)} !=  Qt: {len(detected_cameras)}")

    return detected_cameras, camera_ports


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


def detect_opencv_ports(max_ports: int = 20) -> List[int]:
    port = 0
    ports = []
    while port < max_ports:
        camera_available = _check_camera_available(port)
        if camera_available:
            ports.append(port)
        port += 1

    return ports


if __name__ == "__main__":
    import asyncio
    from pprint import pprint
    from skellycam.app.app_controller.app_controller import create_app_controller

    cameras_out = asyncio.run(detect_available_devices(create_app_controller(multiprocessing.Value('b',False)).app_state))
    pprint(cameras_out, indent=4)

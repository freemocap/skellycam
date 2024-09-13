import logging
from pprint import pprint

import cv2
from PySide6.QtCore import QCoreApplication

from skellycam.api.app.app_state import get_app_state
from skellycam.core.detection.camera_device_info import CameraDeviceInfo

logger = logging.getLogger(__name__)


async def detect_available_devices(check_if_available: bool = False):
    from PySide6.QtMultimedia import QMediaDevices
    # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client
    if not QCoreApplication.instance():
        app = QCoreApplication([])
    else:
        app = QCoreApplication.instance()
    logger.info("Detecting available cameras...")
    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()

    camera_devices = {}
    for camera_number, camera in enumerate(detected_cameras):

        if check_if_available:
            await _check_camera_available(camera_number)

        camera_device_info = CameraDeviceInfo.from_q_camera_device(
            camera_number=camera_number, camera=camera
        )
        camera_devices[camera_device_info.cv2_port] = camera_device_info
    logger.debug(f"Detected camera_devices: {list(camera_devices.keys())}")
    get_app_state().available_devices = {camera_id: device for camera_id, device in camera_devices.items()}


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
    import asyncio
    cameras_out = asyncio.run(detect_available_devices())
    pprint(cameras_out, indent=4)

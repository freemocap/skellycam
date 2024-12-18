import logging
import multiprocessing
import platform
from typing import List, Tuple

import cv2
from PySide6.QtMultimedia import QCameraDevice, QMediaDevices

from skellycam.core import CameraId
from skellycam.system.device_detection.camera_device_info import CameraDeviceInfo, AvailableCameras

logger = logging.getLogger(__name__)

from pygrabber.dshow_graph import FilterGraph

REMOVE_CAMERA_NAMES = ['virtual', 'cam link']
def get_available_cameras(remove_camera_names=None) -> AvailableCameras:
    # https://stackoverflow.com/questions/70886225/get-camera-device-name-and-port-for-opencv-videostream-python
    if remove_camera_names is None:
        remove_camera_names = REMOVE_CAMERA_NAMES
    devices = FilterGraph().get_input_devices()

    available_cameras = {}

    for device_index, device_name in enumerate(devices):
        if any(name in device_name.lower() for name in remove_camera_names):
            logger.debug(f"Skipping camera: {device_name}")
            continue
        available_cameras[CameraId(device_index)] = CameraDeviceInfo.from_pygrabber_device(
            device_index=device_index, device_name=f"{device_name}[{str(device_index)}]"
        )

    return available_cameras

if __name__ == "__main__":
    print(get_available_cameras())
#
# def detect_available_devices(check_if_available: bool = True) -> AvailableDevices:
#
#
#     try:
#         logger.info("Detecting available cameras...")
#         devices = QMediaDevices()
#         detected_cameras = devices.videoInputs()
#
#         if platform.system() == "Darwin":
#             detected_cameras, camera_ports = order_darwin_cameras(detected_cameras=detected_cameras)
#         else:
#             camera_ports = range(len(detected_cameras))
#         remove_virtual_cameras(camera_ports, detected_cameras)
#         camera_devices = {}
#         for camera_number, camera in zip(camera_ports, detected_cameras):
#
#             if check_if_available and not platform.system() == "Darwin":  # macOS cameras get checked in order_darwin_cameras
#                 _check_camera_available(camera_number)
#
#             camera_device_info = CameraDeviceInfo.from_q_camera_device(
#                 camera_number=camera_number, camera=camera
#             )
#             camera_devices[camera_device_info.cv2_port] = camera_device_info
#         logger.debug(f"Detected camera_devices: {list(camera_devices.keys())}")
#         return camera_devices
#     except Exception as e:
#         logger.exception(f"Error detecting available cameras: {e}")
#         raise
#
#
# def order_darwin_cameras(detected_cameras: List[QCameraDevice]) -> Tuple[List[QCameraDevice], List[int]]:
#     """
#     Reorder QMultiMediaDevices to match order of OpenCV ports on macOS.
#
#     Removes virtual cameras, and assumes virtual cameras are always last.
#     Also assumes that once virtual cameras are removed, the order of the cameras from Qt will match the order of OpenCV.
#     """
#     camera_ports = detect_opencv_ports()
#
#     if len(camera_ports) != len(detected_cameras):
#         raise ValueError(
#             f"OpenCV and Qt did not detect same number of cameras: OpenCV: {len(camera_ports)} !=  Qt: {len(detected_cameras)}")
#
#     return detected_cameras, camera_ports
#
#
# def remove_virtual_cameras(camera_ports, detected_cameras):
#     for camera in detected_cameras:
#         if "virtual" in camera.description().lower():
#             detected_cameras.remove(camera)
#             camera_ports.pop()  # assumes virtual camera is always last # TODO - not this lol
#
#
# def _check_camera_available(port: int) -> bool:
#     logger.debug(f"Checking if camera on port: {port} is available...")
#     cap = cv2.VideoCapture(port)
#     success, frame = cap.read()
#     if not cap.isOpened() or not success or frame is None:
#         logger.debug(f"Camera on port: {port} is not available...")
#         return False
#     logger.debug(f"Camera on port: {port} is available!")
#     cap.release()
#     return True
#
#
# def detect_opencv_ports(max_ports: int = 20) -> List[int]:
#     port = 0
#     ports = []
#     while port < max_ports:
#         camera_available = _check_camera_available(port)
#         if camera_available:
#             ports.append(port)
#         port += 1
#
#     return ports
#


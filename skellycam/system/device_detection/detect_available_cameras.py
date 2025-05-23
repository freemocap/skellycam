import logging
import platform
from enum import Enum
from typing import List, Tuple

from skellycam import CameraIndex
from skellycam.system.device_detection.camera_device_info import CameraDeviceInfo, AvailableCameras
from skellycam.system.device_detection.detection_strategies.detect_opencv_ports import detect_opencv_ports, \
    get_available_cameras_opencv

logger = logging.getLogger(__name__)

REMOVE_CAMERA_NAMES = ['virtual', 'cam link']


class CameraDetectionStrategies(Enum):
    OPENCV = "open_cv"
    QT_MULTIMEDIA = "qt_multimedia"
    PYGRABBER = "pygrabber"


def remove_cameras_by_name(remove_camera_names: List[str],
                           available_cameras: AvailableCameras):
    for camera_name in remove_camera_names:
        for camera_id, camera_info in available_cameras.items():
            if camera_name in camera_info.name.lower():
                logger.debug(f"Removing camera: {camera_info.name}")
                available_cameras.pop(camera_id)
                break


def get_available_cameras(strategy: CameraDetectionStrategies, remove_camera_names=None) -> AvailableCameras:
    if remove_camera_names is None:
        remove_camera_names = REMOVE_CAMERA_NAMES

    if strategy == CameraDetectionStrategies.OPENCV:
        return get_available_cameras_opencv()
    elif strategy == CameraDetectionStrategies.QT_MULTIMEDIA:
        return _get_available_cameras_qt_multimedia(remove_camera_names)
    elif strategy == CameraDetectionStrategies.PYGRABBER:
        return _get_available_cameras_pygrabber(remove_camera_names)
    else:
        raise ValueError(f"Unsupported camera detection strategy: {strategy}")


def _get_available_cameras_qt_multimedia(remove_camera_names) -> AvailableCameras:
    from PySide6.QtMultimedia import QMediaDevices, QCameraDevice


    def order_darwin_cameras(detected_cameras: List[QCameraDevice]) -> Tuple[List[QCameraDevice], List[int]]:
        camera_ports = detect_opencv_ports()
        if len(camera_ports) != len(detected_cameras):
            raise ValueError(
                f"OpenCV and Qt did not detect same number of cameras: OpenCV: {len(camera_ports)} !=  Qt: {len(detected_cameras)}")
        return detected_cameras, camera_ports

    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()
    if platform.system() == "Darwin":
        detected_cameras, camera_ports = order_darwin_cameras(detected_cameras=detected_cameras)
    else:
        camera_ports = range(len(detected_cameras))
    remove_virtual_cameras(camera_ports, detected_cameras)
    camera_devices = {}
    for camera_number, camera in zip(camera_ports, detected_cameras):
        # if not platform.system() == "Darwin":
        #     _check_camera_available(camera_number)
        camera_device_info = CameraDeviceInfo.from_q_camera_device(camera_number=camera_number, camera=camera)
        camera_devices[camera_device_info.cv2_port] = camera_device_info
    return camera_devices


def _get_available_cameras_pygrabber(remove_camera_names) -> AvailableCameras:
    from pygrabber.dshow_graph import FilterGraph
    devices = FilterGraph().get_input_devices()
    available_cameras = {}
    for device_index, device_name in enumerate(devices):
        if any(name in device_name.lower() for name in remove_camera_names):
            logger.debug(f"Skipping camera: {device_name}")
            continue
        available_cameras[CameraIndex(device_index)] = CameraDeviceInfo.from_pygrabber_device(
            device_index=device_index, device_name=f"{device_name}[{str(device_index)}]"
        )
    return available_cameras


def remove_virtual_cameras(camera_ports, detected_cameras):
    for camera in detected_cameras:
        if "virtual" in camera.description().lower():
            detected_cameras.remove(camera)
            camera_ports.pop()

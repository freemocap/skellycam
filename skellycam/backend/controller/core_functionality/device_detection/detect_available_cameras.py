from pprint import pprint
from typing import Dict

from PySide6.QtMultimedia import QMediaDevices

from skellycam.models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.models.cameras.camera_id import CameraId


def detect_available_cameras() -> Dict[CameraId, CameraDeviceInfo]:
    devices = QMediaDevices()
    available_cameras = devices.videoInputs()
    cameras = {}
    for camera_number, camera in enumerate(available_cameras):
        if camera.isNull():
            continue
        cameras[camera_number] = CameraDeviceInfo.from_q_camera_device(camera_number=camera_number,
                                                                       camera=camera)
    return cameras


if __name__ == "__main__":
    cameras_out = detect_available_cameras()
    pprint(cameras_out, indent=4)

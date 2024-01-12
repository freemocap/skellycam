from pprint import pprint
from typing import Dict

from PySide6.QtMultimedia import QMediaDevices
from pydantic import BaseModel

from skellycam.backend.models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.backend.models.cameras.camera_id import CameraId


class CamerasDetectedResponse(BaseModel):
    success: bool
    available_cameras: Dict[CameraId, CameraDeviceInfo]


def detect_available_cameras() -> CamerasDetectedResponse:
    devices = QMediaDevices()
    available_cameras = devices.videoInputs()
    cameras = {}
    for camera_number, camera in enumerate(available_cameras):
        if camera.isNull():
            continue
        cameras[camera_number] = CameraDeviceInfo.from_q_camera_device(
            camera_number=camera_number, camera=camera
        )
    return CamerasDetectedResponse(success=True, available_cameras=cameras)


if __name__ == "__main__":
    cameras_out = detect_available_cameras()
    pprint(cameras_out.available_cameras, indent=4)

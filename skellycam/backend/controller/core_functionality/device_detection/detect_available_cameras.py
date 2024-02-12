from pprint import pprint
from typing import Dict

from PySide6.QtMultimedia import QMediaDevices
from pydantic import BaseModel

from skellycam.backend.models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.backend.models.cameras.camera_id import CameraId

DetectedCameras = Dict[CameraId, CameraDeviceInfo]


class CamerasDetectedResponse(BaseModel):
    detected_cameras: DetectedCameras


def detect_available_cameras() -> CamerasDetectedResponse:
    devices = QMediaDevices()
    detected_cameras = devices.videoInputs()
    cameras = {}
    for camera_number, camera in enumerate(detected_cameras):
        if camera.isNull():
            continue
        cameras[camera_number] = CameraDeviceInfo.from_q_camera_device(
            camera_number=camera_number, camera=camera
        )
    return CamerasDetectedResponse(detected_cameras=cameras)


if __name__ == "__main__":
    cameras_out = detect_available_cameras()
    pprint(cameras_out.detected_cameras, indent=4)

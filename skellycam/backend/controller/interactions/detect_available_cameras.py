from typing import Dict, Optional

from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.backend.controller.interactions.base_models import BaseRequest, BaseResponse, BaseCommand, \
    BaseInteraction
from skellycam.models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.models.cameras.camera_id import CameraId


class DetectAvailableCamerasRequest(BaseRequest):
    """
    A request to detect available cameras and return their info in a `CamerasDetected` response
    """
    pass


class CamerasDetectedResponse(BaseResponse):
    success: bool
    available_cameras: Dict[CameraId, CameraDeviceInfo]


class DetectAvailableCamerasCommand(BaseCommand):
    def execute(self, **kwargs) -> CamerasDetectedResponse:
        available_cameras = detect_available_cameras()
        return CamerasDetectedResponse(success=True,
                                       available_cameras=available_cameras)


class DetectAvailableCamerasInteraction(BaseInteraction):
    request: DetectAvailableCamerasRequest
    command: Optional[DetectAvailableCamerasCommand]
    response: Optional[CamerasDetectedResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=DetectAvailableCamerasRequest.create(**kwargs))

    def execute_command(self, **kwargs) -> CamerasDetectedResponse:
        self.command = DetectAvailableCamerasCommand()
        self.response = self.command.execute()
        return self.response

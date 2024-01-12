from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras, CamerasDetectedResponse

CONTROLLER = None
def get_or_create_controller() -> 'Controller':
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class Controller:

    def __init__(self):
        self.available_cameras = None
        self.camera_group_manager = CameraGroupManager()

    def detect_available_cameras(self) -> CamerasDetectedResponse:
        return detect_available_cameras()

import multiprocessing
from dataclasses import dataclass
from typing import Optional, Callable, TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.core.videos.video_recorder_manager import RecordingInfo

if TYPE_CHECKING:
    from skellycam.api.app.app_state import AppStateDTO

@dataclass
class GUIState(QWidget):

    def __init__(self):
        super().__init__()
        self._cameras_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._kill_camera_group_flag_status: bool = False
        self._record_frames_flag_status: bool = False

        self._recording_info: Optional[RecordingInfo] = None
        self._latest_frontend_payload: Optional[FrontendFramePayload] = None
        self._new_frontend_payload_available: bool = False

        self._lock: multiprocessing.Lock = multiprocessing.Lock()

        self._image_update_callable: Optional[Callable] = None

    def set_image_update_callable(self, update_callable: Callable) -> None:
        self._image_update_callable = update_callable

    def update_app_state(self, app_state_dto: 'AppStateDTO') -> None:
        self.camera_configs = app_state_dto.camera_configs
        self.available_devices = app_state_dto.available_devices
        self.record_frames_flag_status = app_state_dto.record_frames_flag_status
        self.kill_camera_group_flag_status = app_state_dto.kill_camera_group_flag_status


    @property
    def camera_configs(self) -> Optional[CameraConfigs]:
        with self._lock:
            return self._cameras_configs

    @camera_configs.setter
    def camera_configs(self, value: Optional[CameraConfigs]) -> None:
        with self._lock:
            self._cameras_configs = value

    @property
    def available_devices(self) -> Optional[AvailableDevices]:
        with self._lock:
            return self._available_devices

    @available_devices.setter
    def available_devices(self, value: Optional[AvailableDevices]) -> None:
        with self._lock:
            self._available_devices = value

    @property
    def record_frames_flag_status(self) -> bool:
        with self._lock:
            return self._record_frames_flag_status

    @record_frames_flag_status.setter
    def record_frames_flag_status(self, value: bool) -> None:
        with self._lock:
            self._record_frames_flag_status = value

    @property
    def kill_camera_group_flag_status(self) -> bool:
        with self._lock:
            return self._kill_camera_group_flag_status

    @kill_camera_group_flag_status.setter
    def kill_camera_group_flag_status(self, value: bool) -> None:
        with self._lock:
            self._kill_camera_group_flag_status = value

    @property
    def recording_info(self) -> Optional[RecordingInfo]:
        with self._lock:
            return self._recording_info

    @recording_info.setter
    def recording_info(self, value: Optional[RecordingInfo]) -> None:
        with self._lock:
            self._recording_info = value

    @property
    def new_frontend_payload_available(self) -> bool:
        with self._lock:
            return self._new_frontend_payload_available

    @property
    def latest_frontend_payload(self):
        with self._lock:
            self._new_frontend_payload_available = False
            return self._latest_frontend_payload

    @latest_frontend_payload.setter
    def latest_frontend_payload(self, value):
        with self._lock:
            self._new_frontend_payload_available = True
            self._latest_frontend_payload = value
            self._image_update_callable(value)

    @property
    def number_of_frames(self) -> Optional[int]:
        with self._lock:
            if self._recording_info is None:
                return None
            return self._latest_frontend_payload.multi_frame_number + 1

    @property
    def number_of_cameras(self) -> Optional[int]:
        with self._lock:
            if self._cameras_configs is None:
                return None
            return len(self._latest_frontend_payload.jpeg_images)


GUI_STATE = None


def get_gui_state() -> GUIState:
    global GUI_STATE
    if GUI_STATE is None:
        GUI_STATE = GUIState()
    return GUI_STATE



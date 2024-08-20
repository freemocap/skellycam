import multiprocessing
from dataclasses import dataclass
from typing import Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload


@dataclass
class GUIState:
    _cameras_configs: Optional[CameraConfigs] = None
    _available_devices: Optional[AvailableDevices] = None
    _is_recording: bool = False
    _recording_save_folder: Optional[str] = None
    _latest_frontend_payload: Optional[FrontendFramePayload] = None
    _new_frontend_payload_available: bool = False

    _lock: multiprocessing.Lock = multiprocessing.Lock()

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
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    @is_recording.setter
    def is_recording(self, value: bool) -> None:
        with self._lock:
            self._is_recording = value

    @property
    def recording_save_folder(self) -> Optional[str]:
        with self._lock:
            return self._recording_save_folder

    @recording_save_folder.setter
    def recording_save_folder(self, value: Optional[str]) -> None:
        with self._lock:
            self._recording_save_folder = value

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


GUI_STATE = None


def get_gui_state() -> GUIState:
    global GUI_STATE
    if GUI_STATE is None:
        GUI_STATE = GUIState()
    return GUI_STATE


def reset_gui_state() -> None:
    global GUI_STATE
    GUI_STATE = GUIState()
    return GUI_STATE

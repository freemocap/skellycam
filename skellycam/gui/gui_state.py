import multiprocessing
from dataclasses import dataclass
from typing import Optional, Callable

from PySide6.QtWidgets import QWidget

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.frames.frame_saver import RecordingInfo
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload


@dataclass
class GUIState(QWidget):
    _cameras_configs: Optional[CameraConfigs] = None
    _available_devices: Optional[AvailableDevices] = None
    _is_recording: bool = False
    _recording_info: Optional[RecordingInfo] = None
    _latest_frontend_payload: Optional[FrontendFramePayload] = None
    _new_frontend_payload_available: bool = False

    _lock: multiprocessing.Lock = multiprocessing.Lock()

    _image_update_callable: Optional[Callable] = None

    def set_image_update_callable(self, image_update_callable: Callable) -> None:
        with self._lock:
            self._image_update_callable = image_update_callable

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

            if self._image_update_callable is not None:
                self._image_update_callable(value)


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

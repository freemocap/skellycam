import multiprocessing
from typing import Optional, Callable, TYPE_CHECKING

import numpy as np
from pydantic import BaseModel

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.core.videos.video_recorder_manager import RecordingInfo

if TYPE_CHECKING:
    from skellycam.api.app.app_state import AppStateDTO


class FramerateStats(BaseModel):
    median_frame_duration_sec: float = 0.0
    std_frame_duration_sec: float = 0.0
    mean_frames_per_second: float = 0.0
    std_frame_per_second: float = 0.0

    @classmethod
    def from_timestamps_ns(cls, timestamps_ns: list[float], max_length: int = 30) -> 'FramerateStats':
        if len(timestamps_ns) < max_length + 1:
            return cls()
        t_diff_sec = np.diff(timestamps_ns[:-max_length]) / 1e6
        median_t_diff = np.median(t_diff_sec)
        std_t_diff = np.std(t_diff_sec)
        return cls(median_frame_duration_sec=median_t_diff,
                   std_frame_duration_sec=std_t_diff)

    @property
    def median_std_str(self) -> str:
        """
        A compact string representation of the mean and standard deviation of the frame rate.
        """
        return f"Median (Std) Frame Duration: {self.median_frame_duration_sec:.3f} ({self.std_frame_duration_sec:.3f})ms"


class GUIState:

    def __init__(self):
        super().__init__()
        self._mean_frontend_framerate = 0.0
        self._cameras_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._kill_camera_group_flag_status: bool = False
        self._record_frames_flag_status: bool = False

        self._recording_info: Optional[RecordingInfo] = None
        self._new_frontend_payload_available: bool = False

        self._latest_frontend_payload: Optional[FrontendFramePayload] = None
        self._frame_number: Optional[int] = None
        self._timestamps_ns: list[float] = []

        self._lock: multiprocessing.Lock = multiprocessing.Lock()

        self._image_update_callable: Optional[Callable] = None

    def set_image_update_callable(self, image_update_callable: Callable) -> None:
        self._image_update_callable: Optional[Callable] = image_update_callable


    def update_app_state(self, app_state_dto: 'AppStateDTO') -> None:
        self.camera_configs = app_state_dto.camera_configs
        self.available_devices = app_state_dto.available_devices
        self.record_frames_flag_status = app_state_dto.record_frames_flag_status
        self.kill_camera_group_flag_status = app_state_dto.kill_camera_group_flag_status

    @property
    def camera_ids(self):
        if self._cameras_configs:
            return list(self._cameras_configs.keys())
        return []

    @property
    def frontend_framerate_stats(self) -> FramerateStats:
        with self._lock:
            return FramerateStats.from_timestamps_ns(self._timestamps_ns)


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
    def number_of_cameras(self) -> Optional[int]:
        with self._lock:
            if self._cameras_configs is None:
                return None
            return len(self._latest_frontend_payload.jpeg_images)

    @property
    def latest_frontend_payload(self) -> Optional[FrontendFramePayload]:
        with self._lock:
            return self._latest_frontend_payload

    @latest_frontend_payload.setter
    def latest_frontend_payload(self, value: Optional[FrontendFramePayload]) -> None:
        with self._lock:
            self._latest_frontend_payload = value
            self._frame_number = value.multi_frame_number
            if value.multi_frame_number > 30:
                self._timestamps_ns.append(value.timestamp_unix_seconds)
            if self._image_update_callable:
                self._image_update_callable(value)
    
    @property
    def frame_number(self) -> Optional[int]:
        with self._lock:
            if self._latest_frontend_payload is None:
                return None
            return self._latest_frontend_payload.multi_frame_number
    

GUI_STATE = None


def get_gui_state() -> GUIState:
    global GUI_STATE
    if GUI_STATE is None:
        GUI_STATE = GUIState()
    return GUI_STATE



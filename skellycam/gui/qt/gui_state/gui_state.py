import threading
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QMutex, QMutexLocker, Signal
from PySide6.QtWidgets import QWidget

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.recorders.videos.video_recorder_manager import RecordingInfo
from skellycam.gui.qt.gui_state.models.camera_view_sizes import CameraViewSizes
from skellycam.system.device_detection.camera_device_info import AvailableDevices
from skellycam.system.device_detection.detect_available_camerass import detect_available_devices

if TYPE_CHECKING:
    from skellycam.app.app_state import AppStateDTO

import logging

logger = logging.getLogger(__name__)


class GUIState(QWidget):
    new_image_data_available = Signal(dict, bool)

    def __init__(self, parent:QWidget):
        super().__init__(parent=parent)
        self._user_selected_camera_configs: Optional[CameraConfigs] = None
        self._connected_camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None

        self._kill_camera_group_flag_status: bool = False
        self._record_frames_flag_status: bool = False

        self._recording_info: Optional[RecordingInfo] = None
        self._new_frontend_payload_available: bool = False

        self._latest_frontend_payload: Optional[FrontendFramePayload] = None
        self._frame_number: Optional[int] = None

        self._camera_view_sizes: Optional[CameraViewSizes] = CameraViewSizes()

        self._latest_app_state_dto: Optional['AppStateDTO'] = None

        self._mutex_lock = QMutex()

        self._detect_available_devices_task: Optional[threading.Thread] = None



    def update_app_state(self, app_state_dto: 'AppStateDTO') -> None:
        with QMutexLocker(self._mutex_lock):
            self._latest_app_state_dto = app_state_dto

            self._record_frames_flag_status = app_state_dto.record_frames_flag_status

            self._available_devices = app_state_dto.available_devices
            self._connected_camera_configs = app_state_dto.connected_camera_configs
            if self._user_selected_camera_configs is None:
                self._user_selected_camera_configs = app_state_dto.connected_camera_configs

    @property
    def sub_process_statuses(self) -> Optional[str]:
        with QMutexLocker(self._mutex_lock):
            return self._latest_app_state_dto.model_dump_json(indent=2, include={
                'subprocess_statuses', 'task_statuses'}) if self._latest_app_state_dto else None

    @property
    def connected_camera_ids(self):
        with QMutexLocker(self._mutex_lock):
            if self._connected_camera_configs:
                return list(self._connected_camera_configs.keys())
        return []

    @property
    def connected_camera_configs(self) -> Optional[CameraConfigs]:
        with QMutexLocker(self._mutex_lock):
            return self._connected_camera_configs

    @property
    def user_selected_camera_configs(self) -> Optional[CameraConfigs]:
        with QMutexLocker(self._mutex_lock):
            return self._user_selected_camera_configs

    @user_selected_camera_configs.setter
    def user_selected_camera_configs(self, value: CameraConfigs):
        with QMutexLocker(self._mutex_lock):
            self._user_selected_camera_configs = value

    @property
    def available_devices(self) -> Optional[AvailableDevices]:
        with QMutexLocker(self._mutex_lock):
            return self._available_devices

    @available_devices.setter
    def available_devices(self, value: Optional[AvailableDevices]) -> None:
        with QMutexLocker(self._mutex_lock):
            self._available_devices = value

    @property
    def record_frames_flag_status(self) -> bool:
        with QMutexLocker(self._mutex_lock):
            return self._record_frames_flag_status

    @record_frames_flag_status.setter
    def record_frames_flag_status(self, value: bool) -> None:
        with QMutexLocker(self._mutex_lock):
            self._record_frames_flag_status = value

    @property
    def recording_info(self) -> Optional[RecordingInfo]:
        with QMutexLocker(self._mutex_lock):
            return self._recording_info

    @recording_info.setter
    def recording_info(self, value: Optional[RecordingInfo]) -> None:
        with QMutexLocker(self._mutex_lock):
            self._recording_info = value

    @property
    def number_of_cameras(self) -> Optional[int]:
        with QMutexLocker(self._mutex_lock):
            if self._user_selected_camera_configs is None:
                return None
            return len(self._user_selected_camera_configs)



    @property
    def camera_view_sizes(self) -> CameraViewSizes:
        with QMutexLocker(self._mutex_lock):
            return self._camera_view_sizes

    @camera_view_sizes.setter
    def camera_view_sizes(self, value: CameraViewSizes) -> None:
        with QMutexLocker(self._mutex_lock):
            self._camera_view_sizes = value

    def _handle_cameras_close(self):
        with QMutexLocker(self._mutex_lock):
            self._recent_metadata = None
            self._latest_frontend_payload = None
            self._camera_view_sizes = CameraViewSizes()
            self._connected_camera_configs = None


    def detect_available_devices(self):
        def update_available_devices():
            self._available_devices = detect_available_devices()
        self._detect_available_devices_task = threading.Thread(target=update_available_devices)
        self._detect_available_devices_task.start()
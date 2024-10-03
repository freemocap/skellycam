from typing import Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import QMutex, QMutexLocker
from PySide6.QtWidgets import QWidget

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.videos.video_recorder_manager import RecordingInfo
from skellycam.gui.qt.gui_state.models.camera_view_sizes import CameraViewSizes
from skellycam.gui.qt.gui_state.models.recent_multiframe_metadata import RecentMultiframeMetadata

if TYPE_CHECKING:
    from skellycam.api.app.app_state import AppStateDTO


class GUIState(QWidget):

    def __init__(self):
        super().__init__()
        self._user_selected_camera_configs: Optional[CameraConfigs] = None
        self._connected_camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._kill_camera_group_flag_status: bool = False
        self._record_frames_flag_status: bool = False

        self._recording_info: Optional[RecordingInfo] = None
        self._new_frontend_payload_available: bool = False

        self._latest_frontend_payload: Optional[FrontendFramePayload] = None
        self._mean_frontend_framerate = 0.0
        self._recent_metadata: Optional[RecentMultiframeMetadata] = None
        self._frame_number: Optional[int] = None

        self._camera_view_sizes: Optional[CameraViewSizes] = CameraViewSizes()

        self._latest_app_state_dto: Optional['AppStateDTO'] = None

        self._mutex_lock = QMutex()

        self._image_update_callable: Optional[Callable] = None

    def set_image_update_callable(self, image_update_callable: Callable) -> None:
        with QMutexLocker(self._mutex_lock):
            self._image_update_callable: Optional[Callable] = image_update_callable

    def update_app_state(self, app_state_dto: 'AppStateDTO') -> None:
        with QMutexLocker(self._mutex_lock):
            self._latest_app_state_dto = app_state_dto

            self._record_frames_flag_status = app_state_dto.record_frames_flag_status
            self._kill_camera_group_flag_status = app_state_dto.kill_camera_group_flag_status

            self._available_devices = app_state_dto.available_devices
            self._connected_camera_configs = app_state_dto.camera_configs
            if self._user_selected_camera_configs is None:
                self._user_selected_camera_configs = app_state_dto.camera_configs

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
    def kill_camera_group_flag_status(self) -> bool:
        with QMutexLocker(self._mutex_lock):
            return self._kill_camera_group_flag_status

    @kill_camera_group_flag_status.setter
    def kill_camera_group_flag_status(self, value: bool) -> None:
        with QMutexLocker(self._mutex_lock):
            self._kill_camera_group_flag_status = value

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
    def latest_frontend_payload(self) -> Optional[FrontendFramePayload]:
        with QMutexLocker(self._mutex_lock):
            return self._latest_frontend_payload

    @latest_frontend_payload.setter
    def latest_frontend_payload(self, value: Optional[FrontendFramePayload]) -> None:
        with QMutexLocker(self._mutex_lock):
            self._latest_frontend_payload = value
            self._frame_number = value.multi_frame_number
            if not self._recent_metadata or self._recent_metadata.camera_ids != value.camera_ids:
                self._recent_metadata = RecentMultiframeMetadata.from_multi_frame_metadata(value.multi_frame_metadata)
            else:  # don't log the first frame
                self._recent_metadata.add_multiframe_metadata(value.multi_frame_metadata)
            if self._image_update_callable:
                self._image_update_callable(jpeg_images=value.jpeg_images,
                                            framerate_stats_by_camera=self._recent_metadata.framerate_stats_by_camera,
                                            recording_in_progress=self._record_frames_flag_status)

    @property
    def frame_number(self) -> Optional[int]:
        with QMutexLocker(self._mutex_lock):
            if self._latest_frontend_payload is None:
                return None
            return self._latest_frontend_payload.multi_frame_number

    @property
    def camera_view_sizes(self) -> CameraViewSizes:
        with QMutexLocker(self._mutex_lock):
            return self._camera_view_sizes

    @camera_view_sizes.setter
    def camera_view_sizes(self, value: CameraViewSizes) -> None:
        with QMutexLocker(self._mutex_lock):
            self._camera_view_sizes = value

GUI_STATE = None


def get_gui_state() -> GUIState:
    global GUI_STATE
    if GUI_STATE is None:
        GUI_STATE = GUIState()
    return GUI_STATE

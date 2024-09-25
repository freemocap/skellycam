import multiprocessing
from typing import Optional, Callable, TYPE_CHECKING, List, Dict

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frames.payloads.multi_frame_payload import MultiFrameMetadata
from skellycam.core.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping
from skellycam.core.videos.video_recorder_manager import RecordingInfo
from skellycam.utilities.sample_statistics import DescriptiveStatistics

if TYPE_CHECKING:
    from skellycam.api.app.app_state import AppStateDTO


class CameraFramerateStats(BaseModel):
    camera_id: CameraId
    frame_number: int = 0
    utc_mapping: UtcToPerfCounterMapping
    previous_frame_utc_ns: int

    frame_durations_ms: List[float] = []
    duration_stats: Optional[DescriptiveStatistics] = None

    max_length: int = 100

    @property
    def timestamps_unix_seconds_by_camera(self):
        return [metadata.timestamp_unix_seconds for metadata in self.recent_metadata]

    @classmethod
    def from_frame_metadata(cls,
                            frame_metadata: FrameMetadata,
                            utc_mapping: UtcToPerfCounterMapping
                            ) -> 'CameraFramerateStats':
        return cls(camera_id=frame_metadata.camera_id,
                   frame_number=frame_metadata.frame_number,
                   previous_frame_utc_ns=utc_mapping.convert_perf_counter_ns_to_unix_ns(
                       perf_counter_ns=frame_metadata.timestamp_ns),
                   utc_mapping=utc_mapping)

    def add_frame_metadata(self, frame_metadata: FrameMetadata):
        utc_timestamp_ns = self.utc_mapping.convert_perf_counter_ns_to_unix_ns(
            perf_counter_ns=frame_metadata.timestamp_ns)
        frame_duration_ns = utc_timestamp_ns - self.previous_frame_utc_ns
        self.previous_frame_utc_ns = utc_timestamp_ns
        self.frame_durations_ms.append(frame_duration_ns / 1e6)
        if len(self.frame_durations_ms) > self.max_length:
            self.frame_durations_ms.pop(0)

        if len(self.frame_durations_ms) < 30:
            return None

        self.duration_stats = DescriptiveStatistics.from_samples(
            name=f"Camera-{self.camera_id} Frame Duration Statistics",
            sample_data=self.frame_durations_ms)

    @property
    def duration_mean_std_ms_str(self):
        if self.duration_stats is None:
            return "N/A"
        return f"{self.duration_stats.mean:.2f}({self.duration_stats.standard_deviation:.2f})ms"

    @property
    def fps_mean_str(self):
        if self.duration_stats is None:
            return "N/A"
        return f"{1 / (self.duration_stats.mean * .001):.2f}"


class RecentMultiframeMetadata(BaseModel):
    recent_metadata: List[MultiFrameMetadata] = []
    framerate_stats_by_camera: Dict[CameraId, CameraFramerateStats] = {}
    max_recent_metadata: int = 30
    camera_ids: List[CameraId]

    @classmethod
    def from_multi_frame_metadata(cls, multi_frame_metadata: MultiFrameMetadata) -> 'RecentMultiframeMetadata':
        return cls(recent_metadata=[multi_frame_metadata],
                   framerate_stats_by_camera={
                       camera_id: CameraFramerateStats.from_frame_metadata(frame_metadata=frame_metadata,
                                                                           utc_mapping=multi_frame_metadata.utc_ns_to_perf_ns
                                                                           )
                       for camera_id, frame_metadata in multi_frame_metadata.frame_metadata_by_camera.items()
                   },
                   camera_ids=list(multi_frame_metadata.frame_metadata_by_camera.keys())
                   )

    def add_multiframe_metadata(self, metadata: MultiFrameMetadata):
        if self.camera_ids != list(metadata.frame_metadata_by_camera.keys()):
            raise ValueError("Camera IDs do not match")
        self.recent_metadata.append(metadata)
        if len(self.recent_metadata) > self.max_recent_metadata:
            self.recent_metadata.pop(0)

        for camera_id, frame_metadata in metadata.frame_metadata_by_camera.items():
            if camera_id not in self.framerate_stats_by_camera:
                self.framerate_stats_by_camera[camera_id] = CameraFramerateStats.from_frame_metadata(
                    frame_metadata=frame_metadata,
                    utc_mapping=metadata.utc_ns_to_perf
                )
            self.framerate_stats_by_camera[camera_id].add_frame_metadata(frame_metadata)


class CameraViewSizes(BaseModel):
    sizes: Dict[CameraId, Dict[str, int]] = {}
    epsilon: int = 50 # pixels differences less than this are considered equal

    def __eq__(self, other):
        if not isinstance(other, CameraViewSizes):
            return False
        if len(self.sizes) != len(other.sizes):
            return False
        for camera_id, view_size in self.sizes.items():
            if camera_id not in other.sizes:
                return False
            for key, value in view_size.items():
                if key not in other.sizes[camera_id]:
                    return False
                if abs(value - other.sizes[camera_id][key]) > self.epsilon:
                    return False
        return True

    def too_small(self) -> bool:
        # returns True if any view size is less than threshold
        for camera_id, view_size in self.sizes.items():
            if view_size["width"] < self.epsilon or view_size["height"] < self.epsilon:
                return True

class GUIState:

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

        self._lock: multiprocessing.Lock = multiprocessing.Lock()

        self._image_update_callable: Optional[Callable] = None

    def set_image_update_callable(self, image_update_callable: Callable) -> None:
        with self._lock:
            self._image_update_callable: Optional[Callable] = image_update_callable

    def update_app_state(self, app_state_dto: 'AppStateDTO') -> None:
        with self._lock:
            self._latest_app_state_dto = app_state_dto

            self._record_frames_flag_status = app_state_dto.record_frames_flag_status
            self._kill_camera_group_flag_status = app_state_dto.kill_camera_group_flag_status

            self._available_devices = app_state_dto.available_devices
            self._connected_camera_configs = app_state_dto.camera_configs
            if self._user_selected_camera_configs is None:
                self._user_selected_camera_configs = app_state_dto.camera_configs

    @property
    def sub_process_statuses(self) -> Optional[str]:
        with self._lock:
            return self._latest_app_state_dto.model_dump_json(indent=2, include={
                'subprocess_statuses', 'task_statuses'}) if self._latest_app_state_dto else None

    @property
    def connected_camera_ids(self):
        with self._lock:
            if self._connected_camera_configs:
                return list(self._connected_camera_configs.keys())
        return []

    @property
    def connected_camera_configs(self) -> Optional[CameraConfigs]:
        with self._lock:
            return self._connected_camera_configs

    @property
    def user_selected_camera_configs(self) -> Optional[CameraConfigs]:
        with self._lock:
            return self._user_selected_camera_configs

    @user_selected_camera_configs.setter
    def user_selected_camera_configs(self, value: CameraConfigs):
        with self._lock:
            self._user_selected_camera_configs = value

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
            if self._user_selected_camera_configs is None:
                return None
            return len(self._user_selected_camera_configs)

    @property
    def latest_frontend_payload(self) -> Optional[FrontendFramePayload]:
        with self._lock:
            return self._latest_frontend_payload

    @latest_frontend_payload.setter
    def latest_frontend_payload(self, value: Optional[FrontendFramePayload]) -> None:
        with self._lock:
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
        with self._lock:
            if self._latest_frontend_payload is None:
                return None
            return self._latest_frontend_payload.multi_frame_number

    @property
    def camera_view_sizes(self) -> CameraViewSizes:
        with self._lock:
            return self._camera_view_sizes

    @camera_view_sizes.setter
    def camera_view_sizes(self, value: CameraViewSizes) -> None:
        with self._lock:
            self._camera_view_sizes = value

GUI_STATE = None


def get_gui_state() -> GUIState:
    global GUI_STATE
    if GUI_STATE is None:
        GUI_STATE = GUIState()
    return GUI_STATE

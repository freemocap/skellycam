import multiprocessing
from dataclasses import dataclass, field
from multiprocessing.managers import DictProxy

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraIdString

def validate_camera_configs(camera_configs: CameraConfigs) -> None:
    if not camera_configs:
        raise ValueError("Camera configurations cannot be empty.")
    if len([config for config in camera_configs.values() if config.principal_camera]) != 1:
        raise ValueError("There must be exactly one principal camera in the camera group.")

@dataclass
class CameraGroupIPC:
    camera_configs: DictProxy = field(default_factory=lambda: multiprocessing.Manager().dict())
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    shutdown_camera_group_flag: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value("b", False))
    record_frames_flag: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value('b', False))
    recording_info_queue: multiprocessing.Queue = field(default_factory=multiprocessing.Queue)

    @classmethod
    def from_configs(cls, camera_configs: CameraConfigs) -> "CameraGroupIPC":
        instance = cls()
        for camera_id, config in camera_configs.items():
            instance.set_config_by_id(camera_id=camera_id, camera_config=config)
        validate_camera_configs(dict(instance.camera_configs))
        return instance

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())

    @property
    def should_continue(self) -> bool:
        return not self.shutdown_camera_group_flag.value

    @should_continue.setter
    def should_continue(self, value: bool) -> None:
        self.shutdown_camera_group_flag.value = not value

    def get_config_by_id(self, camera_id: str, with_lock: bool) -> CameraConfig:
        config: CameraConfig | None = None
        if not with_lock:
            config = self.camera_configs.get(camera_id)
        else:
            with self.lock:
                config = self.camera_configs.get(camera_id)
        if config is None:
            raise ValueError(f"Camera ID {camera_id} not found in camera configs.")
        return config

    def set_config_by_id(self, camera_id: str, camera_config: CameraConfig | None) -> None:
        if self.record_frames_flag.value:
            raise ValueError("Cannot update camera configuration while recording is in progress.")
        with self.lock:
            self.camera_configs[camera_id] = camera_config
            validate_camera_configs(dict(self.camera_configs))

    def start_recording(self, recording_info: RecordingInfo) -> None:
        if self.record_frames_flag.value:
            raise ValueError("Cannot start recording while recording is in progress.")
        self.recording_info_queue.put(recording_info)
        self.record_frames_flag.value = True

    def stop_recording(self) -> None:
        if not self.record_frames_flag.value:
            raise ValueError("Cannot stop recording - no recording is in progress.")
        self.record_frames_flag.value = False

    def close_camera_group(self) -> None:
        if self.record_frames_flag.value:
            self.stop_recording()
        self.shutdown_camera_group_flag.value = True

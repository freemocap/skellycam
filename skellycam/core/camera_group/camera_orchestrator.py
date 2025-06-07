import logging
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_connecton import CameraConnection
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)


@dataclass
class CameraOrchestrator:
    connections: dict[CameraIdString, CameraConnection]

    @classmethod
    def from_configs(cls, camera_configs:CameraConfigs):
        return  cls(connections={
            camera_id: CameraConnection.create(config) for camera_id, config in camera_configs.items()
        })

    @property
    def all_cameras_ready(self):
        return all([conn.status.ready for conn in self.connections.values()])

    @property
    def any_cameras_paused(self):
        return any([conn.status.paused for conn in self.connections.values()])

    @property
    def all_cameras_paused(self):
        return all([conn.status.paused for conn in self.connections.values()])

    @property
    def any_recording(self):
        return any([conn.status.recording for conn in self.connections.values()])

    @property
    def all_recording(self):
        return all([conn.status.recording for conn in self.connections.values()])

    @property
    def camera_frame_counts(self) -> dict[CameraIdString, int]:
        return {camera_id: conn.status.frame_count.value for camera_id, conn in self.connections.items()}

    def should_grab_by_id(self, camera_id: CameraIdString) -> bool:
        if not camera_id in self.connections:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.connections.keys()}")

        if not self.all_cameras_ready:
            return False

        return self.all_camera_counts_greater_than_or_equal_to_camera(camera_id)

    def all_camera_counts_greater_than_or_equal_to_camera(self, camera_id: CameraIdString) -> bool:
        frame_counts = self.camera_frame_counts
        if camera_id not in frame_counts:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.connections.keys()}")

        if all(frame_counts[camera_id] <= count for count in frame_counts.values()):
            return True
        return False

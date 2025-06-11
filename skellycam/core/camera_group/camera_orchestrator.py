import logging
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.status_models import CameraStatus
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)


@dataclass
class CameraOrchestrator:
    camera_statuses: dict[CameraIdString, CameraStatus]

    def add_camera(self,  config: CameraConfig):

        if config.camera_id in self.camera_statuses:
            raise ValueError(f"Camera ID {config.camera_id} already exists in orchestrator.")
        self.camera_statuses[config.camera_id] = CameraStatus()

    def remove_camera(self, camera_id: CameraIdString):
        if camera_id not in self.camera_statuses:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.camera_statuses.keys()}")
        self.camera_statuses[camera_id].should_close.value = True
        del self.camera_statuses[camera_id]

    @classmethod
    def from_camera_ids(cls, camera_ids: list[CameraIdString]):
        return  cls(camera_statuses={
            camera_id: CameraStatus() for camera_id in camera_ids
        })

    @property
    def all_cameras_ready(self):
        return all([status.ready for status in self.camera_statuses.values()])

    @property
    def any_cameras_paused(self):
        return any([status.is_paused.value for status in self.camera_statuses.values()])

    @property
    def all_cameras_paused(self):
        return all([status.is_paused.value for status in self.camera_statuses.values()])

    @property
    def camera_frame_counts(self) -> dict[CameraIdString, int]:
        return {camera_id: status.frame_count.value for camera_id, status in self.camera_statuses.items()}

    def should_grab_by_id(self, camera_id: CameraIdString) -> bool:
        if not camera_id in self.camera_statuses:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.camera_statuses.keys()}")

        if not self.all_cameras_ready:
            return False

        return self.all_camera_counts_greater_than_or_equal_to_camera(camera_id)

    def all_camera_counts_greater_than_or_equal_to_camera(self, camera_id: CameraIdString) -> bool:
        frame_counts = self.camera_frame_counts
        if camera_id not in frame_counts:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.camera_statuses.keys()}")

        if all(frame_counts[camera_id] <= count for count in frame_counts.values()):
            return True
        return False

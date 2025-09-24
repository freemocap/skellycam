import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


@dataclass
class CameraOrchestrator:
    camera_statuses: dict[CameraIdString, CameraStatus]
    first_recording_frame_number: multiprocessing.Value
    last_recording_frame_number: multiprocessing.Value

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_statuses.keys())

    @classmethod
    def from_statuses(cls, camera_statuses: dict[CameraIdString, CameraStatus]) -> 'CameraOrchestrator':
        return cls(camera_statuses=camera_statuses,
                   first_recording_frame_number=multiprocessing.Value("q", -1),
                   last_recording_frame_number=multiprocessing.Value("q", -1))

    @property
    def all_ready(self) -> bool:
        return all([status.ready for status in self.camera_statuses.values()])

    @property
    def any_alive(self) -> bool:
        return self.ipc.camera_orchestrator.any_cameras_alive

    @property
    def all_alive(self) -> bool:
        return all([not status.closed.value for status in self.ipc.camera_orchestrator.camera_statuses.values()])

    @property
    def all_cameras_recording(self):
        return all([status.recording_in_progress.value for status in self.camera_statuses.values()])

    @property
    def all_cameras_paused(self):
        return all([status.is_paused.value for status in self.camera_statuses.values()])

    @property
    def any_cameras_paused(self):
        return any([status.is_paused.value for status in self.camera_statuses.values()])

    @property
    def any_cameras_alive(self) -> bool:
        return any([not status.closed.value for status in self.camera_statuses.values()])


    @property
    def camera_frame_counts(self) -> dict[CameraIdString, int]:
        return {camera_id: status.frame_count.value for camera_id, status in self.camera_statuses.items()}

    def should_record_frame_number(self, frame_number: int) -> tuple[bool, bool]:

        should_record_frame = False
        should_finish_recording = False
        if self.first_recording_frame_number.value != -1 and frame_number >= self.first_recording_frame_number.value:
            should_record_frame = True

        if self.last_recording_frame_number.value != -1:
            if frame_number < self.last_recording_frame_number.value:
                should_record_frame = True
            elif frame_number >= self.last_recording_frame_number.value:
                should_record_frame = False
                should_finish_recording = True

        return should_record_frame, should_finish_recording

    def should_grab_by_id(self, camera_id: CameraIdString) -> bool:
        if not camera_id in self.camera_statuses:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.camera_statuses.keys()}")

        if not self.all_cameras_ready:
            return False

        return self._all_camera_counts_greater_than_or_equal_to_camera(camera_id)

    def _all_camera_counts_greater_than_or_equal_to_camera(self, camera_id: CameraIdString) -> bool:

        if all(self.camera_frame_counts[camera_id] <= count for count in self.camera_frame_counts.values()):
            return True
        return False

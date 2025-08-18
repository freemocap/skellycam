import logging
import multiprocessing
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, SkipValidation, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.wait_functions import wait_10ms, wait_100ms

logger = logging.getLogger(__name__)


class CameraStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True
                              )
    running: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    connected: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    grabbing_frame: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    closing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    recording_in_progress: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    is_recording_frame: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    is_paused: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))

    frame_count: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("q", -1))

    @property
    def ready(self) -> bool:
        return all([self.connected.value,
                    self.running.value,
                    not self.closing.value,
                    not self.closed.value,
                    not self.updating.value,
                    not self.error.value,
                    ])

    def signal_error(self):
        self.error.value = True
        self.connected.value = False
        self.running.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False

    def signal_closing(self):
        self.closing.value = True
        self.running.value = False
        self.grabbing_frame.value = False
        self.is_paused.value = False



@dataclass
class CameraOrchestrator:
    camera_statuses: dict[CameraIdString, CameraStatus]
    first_recording_frame_number: multiprocessing.Value
    last_recording_frame_number: multiprocessing.Value


    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_statuses.keys())


    @classmethod
    def from_camera_ids(cls, camera_ids: list[CameraIdString],
                        first_recording_frame:multiprocessing.Value,
                        last_recording_frame:multiprocessing.Value,
                        ) -> 'CameraOrchestrator':

        return cls(camera_statuses={camera_id: CameraStatus() for camera_id in camera_ids},
                     first_recording_frame_number=first_recording_frame,
                     last_recording_frame_number=last_recording_frame)

    @property
    def all_cameras_ready(self):
        return all([status.ready for status in self.camera_statuses.values()])

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
    def all_cameras_alive(self) -> bool:
        return any([not status.closed.value for status in self.camera_statuses.values()])


    @property
    def camera_frame_counts(self) -> dict[CameraIdString, int]:
        return {camera_id: status.frame_count.value for camera_id, status in self.camera_statuses.items()}

    @property
    def any_grabbing_frame(self) -> bool:
        return any([status.grabbing_frame.value for status in self.camera_statuses.values()])

    @property
    def any_recording_frame(self) -> bool:
        return any([status.is_recording_frame.value for status in self.camera_statuses.values()])

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

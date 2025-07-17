import logging
import multiprocessing
from dataclasses import dataclass

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
    should_record_frames: SkipValidation[multiprocessing.Value]
    first_recording_frame_number: int | None = None
    last_recording_frame_number: int | None = None

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_statuses.keys())


    @classmethod
    def from_camera_ids(cls, camera_ids: list[CameraIdString],
                        should_record_frames: multiprocessing.Value) -> 'CameraOrchestrator':

        return cls(camera_statuses={camera_id: CameraStatus() for camera_id in camera_ids},
                     should_record_frames=should_record_frames,)

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
        if self.first_recording_frame_number is not None or self.last_recording_frame_number is not None:
            if self.first_recording_frame_number is not None and frame_number >= self.first_recording_frame_number:
                should_record_frame = True
            if self.last_recording_frame_number is not None and frame_number <= self.last_recording_frame_number:
                should_record_frame = True
            if self.last_recording_frame_number is not None and frame_number > self.last_recording_frame_number:
                should_finish_recording = True
                self.last_recording_frame_number = None
        return should_record_frame, should_finish_recording

    def should_grab_by_id(self, camera_id: CameraIdString) -> bool:
        if not camera_id in self.camera_statuses:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.camera_statuses.keys()}")

        if not self.all_cameras_ready:
            return False

        return self._all_camera_counts_greater_than_or_equal_to_camera(camera_id)

    def _all_camera_counts_greater_than_or_equal_to_camera(self, camera_id: CameraIdString) -> bool:
        frame_counts = self.camera_frame_counts

        if len(set(list(frame_counts.values()))) == 1:
            # all cameras are on the same frame count - check recording status
            if self.should_record_frames.value and self.first_recording_frame_number is None:
                self.first_recording_frame_number = frame_counts[camera_id]
                logger.api(f"Setting first recording frame number for camera {camera_id} to {self.first_recording_frame_number}")
                self.last_recording_frame_number = None

            if not self.should_record_frames.value and self.first_recording_frame_number is not None:
                self.last_recording_frame_number = frame_counts[camera_id]
                logger.api(f"Setting last recording frame number for camera {camera_id} to {self.last_recording_frame_number}")
                self.first_recording_frame_number = None

        if camera_id not in frame_counts:
            raise ValueError(f"Camera ID {camera_id} not found in orchestrator: {self.camera_statuses.keys()}")

        if all(frame_counts[camera_id] <= count for count in frame_counts.values()):
            return True
        return False

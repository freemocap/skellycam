import logging
from dataclasses import dataclass
from pydantic import BaseModel, Field, SkipValidation, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types import CameraIdString
import multiprocessing

from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True
                              )
    running: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    connected: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    grabbing_frame: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    closing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    should_close: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    should_pause: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    is_paused: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))

    frame_count: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("q", -1))

    @property
    def ready(self) -> bool:
        return all([self.connected.value,
                    self.running.value,
                    not self.should_close.value,
                    not self.closing.value,
                    not self.closed.value,
                    not self.updating.value,
                    not self.should_pause.value,
                    not self.is_paused.value,
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
        self.should_close.value = True



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

    @property
    def any_grabbing_frame(self) -> bool:
        return any([status.grabbing_frame.value for status in self.camera_statuses.values()])
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

    def pause(self, await_paused: bool = True):
        logger.debug(f"Pausing all cameras in orchestrator...")
        for camera_id, status in self.camera_statuses.items():
            if not status.is_paused.value:
                logger.debug(f"Pausing camera {camera_id}...")
                status.should_pause.value = True
        if await_paused:
            while not self.all_cameras_paused:
                logger.debug(f"Waiting for all cameras to pause...")
                wait_10ms()
            logger.debug(f"All cameras paused.")

    def unpause(self, await_unpaused: bool = True):
        logger.debug(f"Unpausing all cameras in orchestrator...")
        for camera_id, status in self.camera_statuses.items():
            if status.is_paused.value:
                logger.debug(f"Unpausing camera {camera_id}...")
                status.should_pause.value = False
        if await_unpaused:
            while self.any_cameras_paused:
                logger.debug(f"Waiting for all cameras to unpause...")
                wait_10ms()
            logger.debug(f"All cameras unpaused.")
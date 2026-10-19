import logging
import multiprocessing
import time
from dataclasses import dataclass
from copy import deepcopy
from multiprocessing.sharedctypes import Synchronized

import numpy as np

from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.wait_functions import await_10ms

logger = logging.getLogger(__name__)

CAMERA_STATE_TIMEOUT_SECONDS = 10.0


@dataclass
class CameraOrchestrator:
    camera_statuses: dict[CameraIdString, CameraStatus]
    first_recording_frame_number: Synchronized
    last_recording_frame_number: Synchronized

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


    async def pause(self, await_paused: bool = True) -> None:
        logger.info("Pausing all cameras...")
        for status in self.camera_statuses.values():
            status.should_pause.value = True

        if await_paused:
            logger.info("Waiting for all cameras to pause...")
            await self._await_pause_state(paused=True)
            logger.trace("All cameras paused.")

    async def unpause(self, await_unpaused: bool = True) -> None:
        logger.info("Unpausing all cameras...")
        for status in self.camera_statuses.values():
            status.should_pause.value = False

        if await_unpaused:
            logger.info("Waiting for all cameras to unpause...")
            await self._await_pause_state(paused=False)
            logger.trace("All cameras unpaused.")

    async def _await_pause_state(self, paused: bool) -> None:
        action = "pause" if paused else "resume"
        deadline = time.monotonic() + CAMERA_STATE_TIMEOUT_SECONDS
        while True:
            unavailable = [
                camera_id for camera_id, status in self.camera_statuses.items()
                if status.error.value or status.closing.value
                or status.closed.value or status.should_close.value
            ]
            if unavailable:
                raise RuntimeError(f"Cannot {action}: cameras failed or closed: {unavailable}")
            pending = [
                camera_id for camera_id, status in self.camera_statuses.items()
                if bool(status.is_paused.value) != paused
            ]
            if not pending:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for cameras to {action}: {pending}")
            await await_10ms()

    def should_record_frame_number(self, frame_number: int | np.integer) -> tuple[bool, bool]:

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

        if not self.all_ready:
            return False

        return self._all_camera_counts_greater_than_or_equal_to_camera(camera_id)

    def _all_camera_counts_greater_than_or_equal_to_camera(self, camera_id: CameraIdString) -> bool:
        counts = deepcopy(self.camera_frame_counts)
        if all(counts[camera_id] <= count for count in counts.values()):
            return True
        return False

    def close(self):
        """Signal closure; CameraManager owns bounded worker joins and escalation."""
        for status in self.camera_statuses.values():
            status.should_close.value = True
        logger.info("Requested closure of all cameras.")
